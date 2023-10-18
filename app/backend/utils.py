import base64
import html
import io
import json
import os
import re
import tiktoken

from asyncio import sleep
from math import ceil
from openai.error import RateLimitError, APIConnectionError
from pypdf import PdfReader, PdfWriter
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

MAX_SECTION_LENGTH = 1000
SENTENCE_SEARCH_LIMIT = 100
SECTION_OVERLAP = 100

SUPPORTED_BATCH_AOAI_MODEL = {"text-embedding-ada-002": {"token_limit": 8100, "max_batch_size": 16}}


def get_data_filepath():
    path = os.path.join(os.getcwd(), "data")
    if not os.path.exists(path):
        os.makedirs(path)
    return path


async def get_ingest_json(container_client):
    ingest = {}
    blob_client = container_client.get_blob_client("ingest.json")
    if await blob_client.exists():
        blob = await blob_client.download_blob()
        filestream = io.BytesIO()
        await blob.readinto(filestream)
        filestream.seek(0)
        try:
            ingest = json.loads(filestream.read().decode("utf-8"))
        except json.JSONDecodeError:
            print("Error parsing JSON")
    return ingest


async def set_ingest_json(container_client, data):
    filestream = io.BytesIO()
    filestream.write((json.dumps(data)).encode("utf-8"))
    filestream.seek(0)
    await container_client.upload_blob("ingest.json", filestream, overwrite=True)


async def is_ingest_lock(container_client):
    blob_client = container_client.get_blob_client("ingest.lock")
    ingest_lock = await blob_client.exists()
    return ingest_lock


async def create_ingest_lock(container_client):
    filestream = io.BytesIO()
    filestream.write("".encode("utf-8"))
    filestream.seek(0)
    await container_client.upload_blob("ingest.lock", filestream, overwrite=True)


async def delete_ingest_lock(container_client):
    await container_client.delete_blob("ingest.lock")


def blob_name_from_file_page(filename, page=0):
    if os.path.splitext(filename)[1].lower() == ".pdf":
        return os.path.splitext(os.path.basename(filename))[0] + f"-{page}" + ".pdf"
    else:
        return os.path.basename(filename)


async def get_all_files(container):
    files = set({})
    blobs = container.list_blob_names()
    async for b in blobs:
        files.add(b)
    all_files = files.union(set(os.listdir(get_data_filepath())))
    return sorted(list(all_files))


async def upload_blobs(blob_container, document_container, filename):
    if not await blob_container.exists():
        await blob_container.create_container()

    if not await document_container.exists():
        await document_container.create_container()

    with open(filename, "rb") as f:
        only_filename = os.path.split(filename)[1]
        print(f"\tUploading blob -> {only_filename}")
        await document_container.upload_blob(only_filename, f, overwrite=True)

    # if file is PDF split into pages and upload each page as a separate blob
    if os.path.splitext(filename)[1].lower() == ".pdf":
        reader = PdfReader(filename)
        pages = reader.pages
        for i in range(len(pages)):
            blob_name = blob_name_from_file_page(filename, i)
            print(f"\tUploading blob for page {i} -> {blob_name}")
            f = io.BytesIO()
            writer = PdfWriter()
            writer.add_page(pages[i])
            writer.write(f)
            f.seek(0)
            await blob_container.upload_blob(blob_name, f, overwrite=True)
    else:
        blob_name = blob_name_from_file_page(filename)
        with open(filename, "rb") as data:
            await blob_container.upload_blob(blob_name, data, overwrite=True)


def table_to_html(table):
    table_html = "<table>"
    rows = [
        sorted([cell for cell in table.cells if cell.row_index == i], key=lambda cell: cell.column_index)
        for i in range(table.row_count)
    ]
    for row_cells in rows:
        table_html += "<tr>"
        for cell in row_cells:
            tag = "th" if (cell.kind == "columnHeader" or cell.kind == "rowHeader") else "td"
            cell_spans = ""
            if cell.column_span > 1:
                cell_spans += f" colSpan={cell.column_span}"
            if cell.row_span > 1:
                cell_spans += f" rowSpan={cell.row_span}"
            table_html += f"<{tag}{cell_spans}>{html.escape(cell.content)}</{tag}>"
        table_html += "</tr>"
    table_html += "</table>"
    return table_html


async def get_document_text(form_recognizer_client, filename, localpdfparser=False):
    offset = 0
    page_map = []
    if localpdfparser:
        reader = PdfReader(filename)
        pages = reader.pages
        for page_num, p in enumerate(pages):
            page_text = p.extract_text()
            page_map.append((page_num, offset, page_text))
            offset += len(page_text)
    else:
        print(f"Extracting text from '{filename}' using Azure Form Recognizer")
        reader = PdfReader(filename)
        number_of_pages = len(reader.pages)
        batch_size = 100
        total_batches = ceil(number_of_pages / 100)
        for offset_page in range(1, number_of_pages + 1, batch_size):
            print(f"Processing Form Recognizer: Batch {ceil(offset_page/batch_size)} of {total_batches} -> {filename}")
            with open(filename, "rb") as f:
                poller = await form_recognizer_client.begin_analyze_document(
                    "prebuilt-layout",
                    document=f,
                    pages=f"{offset_page}-{min(offset_page+batch_size-1, number_of_pages)}",
                )
            form_recognizer_results = await poller.result()
            for page_num, page in enumerate(form_recognizer_results.pages):
                print(f"Processing page {offset_page+page_num} -> {filename}")
                tables_on_page = [
                    table
                    for table in form_recognizer_results.tables
                    if table.bounding_regions[0].page_number == offset_page + page_num
                ]

                # mark all positions of the table spans in the page
                page_offset = page.spans[0].offset
                page_length = page.spans[0].length
                table_chars = [-1] * page_length
                for table_id, table in enumerate(tables_on_page):
                    for span in table.spans:
                        # replace all table spans with "table_id" in table_chars array
                        for i in range(span.length):
                            idx = span.offset - page_offset + i
                            if idx >= 0 and idx < page_length:
                                table_chars[idx] = table_id

                # build page text by replacing characters in table spans with table html
                page_text = ""
                added_tables = set()
                for idx, table_id in enumerate(table_chars):
                    if table_id == -1:
                        page_text += form_recognizer_results.content[page_offset + idx]
                    elif table_id not in added_tables:
                        page_text += table_to_html(tables_on_page[table_id])
                        added_tables.add(table_id)

                page_text += " "
                page_map.append((offset_page - 1 + page_num, offset, page_text))
                offset += len(page_text)

    return page_map


def split_text(page_map, filename):
    SENTENCE_ENDINGS = [".", "!", "?"]
    WORDS_BREAKS = [",", ";", ":", " ", "(", ")", "[", "]", "{", "}", "\t", "\n"]
    print(f"Splitting '{filename}' into sections")

    def find_page(offset):
        num_pages = len(page_map)
        for i in range(num_pages - 1):
            if offset >= page_map[i][1] and offset < page_map[i + 1][1]:
                return i
        return num_pages - 1

    all_text = "".join(p[2] for p in page_map)
    length = len(all_text)
    start = 0
    end = length
    while start + SECTION_OVERLAP < length:
        last_word = -1
        end = start + MAX_SECTION_LENGTH

        if end > length:
            end = length
        else:
            # Try to find the end of the sentence
            while (
                end < length
                and (end - start - MAX_SECTION_LENGTH) < SENTENCE_SEARCH_LIMIT
                and all_text[end] not in SENTENCE_ENDINGS
            ):
                if all_text[end] in WORDS_BREAKS:
                    last_word = end
                end += 1
            if end < length and all_text[end] not in SENTENCE_ENDINGS and last_word > 0:
                end = last_word  # Fall back to at least keeping a whole word
        if end < length:
            end += 1

        # Try to find the start of the sentence or at least a whole word boundary
        last_word = -1
        while (
            start > 0
            and start > end - MAX_SECTION_LENGTH - 2 * SENTENCE_SEARCH_LIMIT
            and all_text[start] not in SENTENCE_ENDINGS
        ):
            if all_text[start] in WORDS_BREAKS:
                last_word = start
            start -= 1
        if all_text[start] not in SENTENCE_ENDINGS and last_word > 0:
            start = last_word
        if start > 0:
            start += 1

        section_text = all_text[start:end]
        yield (section_text, find_page(start))

        last_table_start = section_text.rfind("<table")
        if last_table_start > 2 * SENTENCE_SEARCH_LIMIT and last_table_start > section_text.rfind("</table"):
            # If the section ends with an unclosed table, we need to start the next section with the table.
            # If table starts inside SENTENCE_SEARCH_LIMIT, we ignore it, as that will cause an infinite loop for tables longer than MAX_SECTION_LENGTH
            # If last table starts inside SECTION_OVERLAP, keep overlapping
            print(
                f"Section ends with unclosed table, starting next section with the table at page {find_page(start)} offset {start} table start {last_table_start}"
            )
            start = min(end - SECTION_OVERLAP, start + last_table_start)
        else:
            start = end - SECTION_OVERLAP

    if start + SECTION_OVERLAP < end:
        yield (all_text[start:end], find_page(start))


def filename_to_id(filename):
    filename_ascii = re.sub("[^0-9a-zA-Z_-]", "_", filename)
    filename_hash = base64.b16encode(filename.encode("utf-8")).decode("ascii")
    return f"file-{filename_ascii}-{filename_hash}"


def before_retry_sleep(retry_state):
    print("Rate limited on the OpenAI embeddings API, sleeping before retrying...")


@retry(
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
    wait=wait_random_exponential(min=15, max=60),
    stop=stop_after_attempt(15),
    before_sleep=before_retry_sleep,
)
async def compute_embedding(text, openai, openaihost, embedding_deployment, embedding_model):
    embedding_args = {"deployment_id": embedding_deployment} if openaihost != "openai" else {}
    response = await openai.Embedding.acreate(**embedding_args, model=embedding_model, input=text)
    return response["data"][0]["embedding"]


async def create_sections(filename, page_map, openai, openaihost, embedding_deployment, embedding_model):
    file_id = filename_to_id(filename)
    for i, (content, pagenum) in enumerate(split_text(page_map, filename)):
        print(f"Creating section: {file_id}-page-{pagenum}-section-{i}")
        section = {
            "id": f"{file_id}-page-{pagenum}-section-{i}",
            "content": content,
            "category": "",
            "sourcepage": blob_name_from_file_page(filename, pagenum),
            "sourcefile": filename,
        }
        section["embedding"] = await compute_embedding(
            content, openai, openaihost, embedding_deployment, embedding_model
        )
        yield section


@retry(
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
    wait=wait_random_exponential(min=15, max=60),
    stop=stop_after_attempt(15),
    before_sleep=before_retry_sleep,
)
async def compute_embedding_in_batch(texts, openai, openaihost, openaideployment, openaimodelname):
    embedding_args = {"deployment_id": openaideployment} if openaihost != "openai" else {}
    emb_response = await openai.Embedding.acreate(**embedding_args, model=openaimodelname, input=texts)
    return [data.embedding for data in emb_response.data]


def calculate_tokens_emb_aoai(input: str, openaimodelname):
    encoding = tiktoken.encoding_for_model(openaimodelname)
    return len(encoding.encode(input))


async def update_embeddings_in_batch(filename, page_map, openai, openaihost, openaideployment, openaimodelname):
    batch_queue = []
    copy_s = []
    batch_response = {}
    token_count = 0
    async for s in create_sections(filename, page_map, openai, openaihost, openaideployment, openaimodelname):
        token_count += calculate_tokens_emb_aoai(s["content"], openaimodelname)
        if (
            token_count <= SUPPORTED_BATCH_AOAI_MODEL[openaimodelname]["token_limit"]
            and len(batch_queue) < SUPPORTED_BATCH_AOAI_MODEL[openaimodelname]["max_batch_size"]
        ):
            batch_queue.append(s)
            copy_s.append(s)
        else:
            emb_responses = await compute_embedding_in_batch(
                [item["content"] for item in batch_queue], openai, openaihost, openaideployment, openaimodelname
            )
            print(f"Batch Completed. Batch size  {len(batch_queue)} Token count {token_count}")
            for emb, item in zip(emb_responses, batch_queue):
                batch_response[item["id"]] = emb
            batch_queue = []
            batch_queue.append(s)
            token_count = calculate_tokens_emb_aoai(s["content"], openaimodelname)

    if batch_queue:
        emb_responses = await compute_embedding_in_batch(
            [item["content"] for item in batch_queue], openai, openaihost, openaideployment, openaimodelname
        )
        print(f"Batch Completed. Batch size  {len(batch_queue)} Token count {token_count}")
        for emb, item in zip(emb_responses, batch_queue):
            batch_response[item["id"]] = emb

    for s in copy_s:
        s["embedding"] = batch_response[s["id"]]
        yield s


async def index_sections(filename, sections, search_client, search_index):
    print(f"Indexing sections from '{filename}' into search index '{search_index}'")
    i = 0
    batch = []
    async for s in sections:
        batch.append(s)
        i += 1
        if i % 1000 == 0:
            results = await search_client.upload_documents(documents=batch)
            succeeded = sum([1 for r in results if r.succeeded])
            print(f"\tIndexed {len(results)} sections, {succeeded} succeeded")
            batch = []

    if len(batch) > 0:
        results = await search_client.upload_documents(documents=batch)
        succeeded = sum([1 for r in results if r.succeeded])
        print(f"\tIndexed {len(results)} sections, {succeeded} succeeded")


async def read_files(
    search_client,
    search_index,
    blob_container,
    document_container,
    form_recognizer_client,
    openai,
    openaihost,
    embedding_deployment,
    embedding_model,
):
    """
    Recursively read directory structure under `path_pattern`
    and execute indexing for the individual files
    """
    all_files = await get_all_files(document_container)
    for only_filename in all_files:
        filename = os.path.join(get_data_filepath(), only_filename)
        ingest_json = await get_ingest_json(blob_container)
        file_ingest_properties = ingest_json.get(only_filename, {})
        if file_ingest_properties.get("status") == 0:
            print(f"Processing '{filename}'")
            ingest_json = await get_ingest_json(blob_container)
            ingest_json[only_filename] = {**ingest_json[only_filename], "status": 1}
            await set_ingest_json(blob_container, ingest_json)
            operation = file_ingest_properties.get("operation")
            if operation == 1 or operation == 2:
                await delete_document(
                    blob_container,
                    document_container,
                    search_client,
                    search_index,
                    only_filename,
                    soft_delete=(operation == 1),
                )
            if operation == 0 or operation == 1:
                try:
                    await upload_blobs(blob_container, document_container, filename)
                    page_map = await get_document_text(form_recognizer_client, filename)
                    sections = update_embeddings_in_batch(
                        os.path.basename(filename),
                        page_map,
                        openai,
                        openaihost,
                        embedding_deployment,
                        embedding_model,
                    )
                    await index_sections(
                        os.path.basename(filename),
                        sections,
                        search_client,
                        search_index,
                    )
                    ingest_json = await get_ingest_json(blob_container)
                    ingest_json[os.path.split(filename)[1]] = {"status": 2}
                    await set_ingest_json(blob_container, ingest_json)
                    if os.path.exists(filename):
                        os.remove(filename)
                    print("Indexing successful")
                except Exception as e:
                    print(f"\tGot an error while reading {filename} -> {e} --> skipping file")


async def upload_documents(
    search_client,
    search_index,
    blob_container,
    document_container,
    form_recognizer_client,
    openai,
    openaihost,
    embedding_deployment,
    embedding_model,
):
    print("Processing files...")
    await read_files(
        search_client,
        search_index,
        blob_container,
        document_container,
        form_recognizer_client,
        openai,
        openaihost,
        embedding_deployment,
        embedding_model,
    )
    await delete_ingest_lock(blob_container)


async def filter_blobs(prefix, blobs):
    async for blob in blobs:
        if re.match(f"{prefix}-\\d+\\.pdf", blob):
            yield blob


async def remove_blobs(blob_container, filename, exact_match=False):
    print(f"Removing blobs for '{filename or '<all>'}'")
    if await blob_container.exists():
        if filename is None or exact_match:
            blobs = blob_container.list_blob_names()
        else:
            prefix = os.path.splitext(os.path.basename(filename))[0]
            blobs = filter_blobs(
                prefix,
                blob_container.list_blob_names(name_starts_with=os.path.splitext(os.path.basename(prefix))[0]),
            )
        async for b in blobs:
            if exact_match:
                if b == filename:
                    print(f"\tRemoving blob {b}")
                    await blob_container.delete_blob(b)
            else:
                print(f"\tRemoving blob {b}")
                await blob_container.delete_blob(b)


async def remove_from_index(search_client, search_index, filename):
    print(f"Removing sections from '{filename or '<all>'}' from search index '{search_index}'")
    while True:
        search_filter = None if filename is None else f"sourcefile eq '{os.path.basename(filename)}'"
        r = await search_client.search("", filter=search_filter, top=1000, include_total_count=True)
        if await r.get_count() == 0:
            break
        r = await search_client.delete_documents(documents=[{"id": d["id"]} async for d in r])
        print(f"\tRemoved {len(r)} sections from index")
        # It can take a few seconds for search results to reflect changes, so wait a bit
        await sleep(2)


async def delete_document(blob_container, document_container, search_client, search_index, filename, soft_delete=False):
    await remove_blobs(blob_container, filename)
    await remove_blobs(document_container, filename, exact_match=True)
    await remove_from_index(search_client, search_index, filename)
    if not soft_delete:
        ingest_json = await get_ingest_json(blob_container)
        if filename in ingest_json:
            del ingest_json[filename]
        await set_ingest_json(blob_container, ingest_json)
        full_path = os.path.join(get_data_filepath(), filename)
        if os.path.exists(full_path):
            os.remove(full_path)
