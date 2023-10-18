import io
import json
import logging
import mimetypes
import os
from asyncio import create_task
from typing import AsyncGenerator

import aiohttp
import openai
from azure.ai.formrecognizer.aio import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswParameters,
    PrioritizedFields,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticSettings,
    SimpleField,
    VectorSearch,
    VectorSearchAlgorithmConfiguration,
)
from azure.storage.blob.aio import BlobServiceClient
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from quart import (
    Blueprint,
    Quart,
    abort,
    current_app,
    jsonify,
    make_response,
    request,
    send_file,
    send_from_directory,
)

from approaches.chatreadretrieveread import ChatReadRetrieveReadApproach
from approaches.readdecomposeask import ReadDecomposeAsk
from approaches.readretrieveread import ReadRetrieveReadApproach
from approaches.retrievethenread import RetrieveThenReadApproach
from utils import (
    get_all_files,
    get_data_filepath,
    get_ingest_json,
    set_ingest_json,
    upload_documents,
    is_ingest_lock,
    create_ingest_lock,
)

CONFIG_CREDENTIAL = "azure_credential"
CONFIG_ASK_APPROACHES = "ask_approaches"
CONFIG_CHAT_APPROACHES = "chat_approaches"
CONFIG_SEARCH_INDEX = "search_index"
CONFIG_SEARCH_CLIENT = "search_client"
CONFIG_SEARCH_INDEX_CLIENT = "search_index_client"
CONFIG_BLOB_CONTAINER_CLIENT = "blob_container_client"
CONFIG_BLOB_DOCUMENT_CONTAINER_CLIENT = "blob_document_container_client"
CONFIG_FORM_RECOGNIZER_CLIENT = "form_recognizer_client"
CONFIG_EMBEDDING_MODEL = "embedding_model"
CONFIG_OPENAI_HOST = "openai_host"
CONFIG_AZURE_OPENAI_EMB_DEPLOYMENT = "azure_openai_emb_deployment"

INDEX_FIELDS = [
    SimpleField(name="id", type="Edm.String", key=True),
    SearchableField(name="content", type="Edm.String", analyzer_name="en.microsoft"),
    SearchField(
        name="embedding",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        hidden=False,
        searchable=True,
        filterable=False,
        sortable=False,
        facetable=False,
        vector_search_dimensions=1536,
        vector_search_configuration="default",
    ),
    SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
    SimpleField(name="sourcepage", type="Edm.String", filterable=True, facetable=True),
    SimpleField(name="sourcefile", type="Edm.String", filterable=True, facetable=True),
]

bp = Blueprint("routes", __name__, static_folder="static")


@bp.route("/")
async def index():
    return await bp.send_static_file("index.html")


@bp.route("/favicon.ico")
async def favicon():
    return await bp.send_static_file("favicon.ico")


@bp.route("/assets/<path:path>")
async def assets(path):
    return await send_from_directory("static/assets", path)


# Serve content files from blob storage from within the app to keep the example self-contained.
# *** NOTE *** this assumes that the content files are public, or at least that all users of the app
# can access all the files. This is also slow and memory hungry.
@bp.route("/content/<path>")
async def content_file(path):
    blob_container_client = current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]
    blob = await blob_container_client.get_blob_client(path).download_blob()
    if not blob.properties or not blob.properties.has_key("content_settings"):
        abort(404)
    mime_type = blob.properties["content_settings"]["content_type"]
    if mime_type == "application/octet-stream":
        mime_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    blob_file = io.BytesIO()
    await blob.readinto(blob_file)
    blob_file.seek(0)
    return await send_file(blob_file, mimetype=mime_type, as_attachment=False, attachment_filename=path)


@bp.route("/files")
async def fetch_files():
    all_files = await get_all_files(current_app.config[CONFIG_BLOB_DOCUMENT_CONTAINER_CLIENT])
    return jsonify(
        {
            "files": all_files,
            "ingested": await get_ingest_json(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]),
            "ingest_lock": await is_ingest_lock(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]),
        }
    )


@bp.route("/file/<filename>")
async def fetch_file(filename):
    ingest_json = await get_ingest_json(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT])
    if ingest_json.get(filename, {}).get("status", 0) != 2:
        filepath = os.path.join(get_data_filepath(), filename)
        if os.path.exists(filepath):
            return await send_file(filepath)
        else:
            return jsonify({"error": "Location not found"}), 404
    document_container_client = current_app.config[CONFIG_BLOB_DOCUMENT_CONTAINER_CLIENT]
    blob = await document_container_client.get_blob_client(filename).download_blob()
    if not blob.properties or not blob.properties.has_key("content_settings"):
        return jsonify({"error": "Location not found"}), 404
    mime_type = blob.properties["content_settings"]["content_type"]
    if mime_type == "application/octet-stream":
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    blob_file = io.BytesIO()
    await blob.readinto(blob_file)
    blob_file.seek(0)
    return await send_file(blob_file, mimetype=mime_type, as_attachment=False, attachment_filename=filename)


@bp.route("/upload-files", methods=["POST"])
async def upload_files():
    files = await request.files
    data_path = get_data_filepath()
    ingest_json = await get_ingest_json(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT])
    files = files.to_dict(flat=False)
    for file in files["files"]:
        await file.save(os.path.join(data_path, file.filename))
        ingest_json[file.filename] = {"operation": 0, "status": 0}
    await set_ingest_json(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT], ingest_json)
    all_files = await get_all_files(current_app.config[CONFIG_BLOB_DOCUMENT_CONTAINER_CLIENT])
    return jsonify(
        {
            "files": all_files,
            "ingested": ingest_json,
            "ingest_lock": await is_ingest_lock(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]),
        }
    )


@bp.route("/ingest-files")
async def ingest_files():
    if not await is_ingest_lock(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]):
        await create_ingest_lock(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT])
        create_task(
            upload_documents(
                current_app.config[CONFIG_SEARCH_CLIENT],
                current_app.config[CONFIG_SEARCH_INDEX],
                current_app.config[CONFIG_BLOB_CONTAINER_CLIENT],
                current_app.config[CONFIG_BLOB_DOCUMENT_CONTAINER_CLIENT],
                current_app.config[CONFIG_FORM_RECOGNIZER_CLIENT],
                openai,
                current_app.config[CONFIG_OPENAI_HOST],
                current_app.config[CONFIG_AZURE_OPENAI_EMB_DEPLOYMENT],
                current_app.config[CONFIG_EMBEDDING_MODEL],
            )
        )
        all_files = await get_all_files(current_app.config[CONFIG_BLOB_DOCUMENT_CONTAINER_CLIENT])
        return jsonify(
            {
                "files": all_files,
                "ingested": await get_ingest_json(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]),
                "ingest_lock": await is_ingest_lock(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]),
            }
        )
    return jsonify({"error": "Ingest already in progress"}), 403


@bp.route("/update-file", methods=["POST"])
async def update_file():
    files = await request.files
    data_path = get_data_filepath()
    ingest_json = await get_ingest_json(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT])
    files = files.to_dict(flat=False)
    for file in files["files"]:
        await file.save(os.path.join(data_path, file.filename))
        if ingest_json[file.filename]["status"] == 0:
            ingest_json[file.filename] = {"operation": 0, "status": 0}
        else:
            ingest_json[file.filename] = {"operation": 1, "status": 0}
    await set_ingest_json(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT], ingest_json)
    all_files = await get_all_files(current_app.config[CONFIG_BLOB_DOCUMENT_CONTAINER_CLIENT])
    return jsonify(
        {
            "files": all_files,
            "ingested": ingest_json,
            "ingest_lock": await is_ingest_lock(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]),
        }
    )


@bp.route("/delete-file", methods=["POST"])
async def delete_file():
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    filename = request_json.get("file")
    ingest_json = await get_ingest_json(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT])
    ingest_json[filename] = {"operation": 2, "status": 0}
    await set_ingest_json(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT], ingest_json)
    all_files = await get_all_files(current_app.config[CONFIG_BLOB_DOCUMENT_CONTAINER_CLIENT])
    return jsonify(
        {
            "files": all_files,
            "ingested": ingest_json,
            "ingest_lock": await is_ingest_lock(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]),
        }
    )


@bp.route("/ask", methods=["POST"])
async def ask():
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    approach = request_json["approach"]
    try:
        impl = current_app.config[CONFIG_ASK_APPROACHES].get(approach)
        if not impl:
            return jsonify({"error": "unknown approach"}), 400
        # Workaround for: https://github.com/openai/openai-python/issues/371
        async with aiohttp.ClientSession() as s:
            openai.aiosession.set(s)
            r = await impl.run(request_json["question"], request_json.get("overrides") or {})
        return jsonify(r)
    except Exception as e:
        logging.exception("Exception in /ask")
        return jsonify({"error": str(e)}), 500


@bp.route("/chat", methods=["POST"])
async def chat():
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    approach = request_json["approach"]
    try:
        impl = current_app.config[CONFIG_CHAT_APPROACHES].get(approach)
        if not impl:
            return jsonify({"error": "unknown approach"}), 400
        # Workaround for: https://github.com/openai/openai-python/issues/371
        async with aiohttp.ClientSession() as s:
            openai.aiosession.set(s)
            r = await impl.run_without_streaming(request_json["history"], request_json.get("overrides", {}))
        return jsonify(r)
    except Exception as e:
        logging.exception("Exception in /chat")
        return jsonify({"error": str(e)}), 500


async def format_as_ndjson(r: AsyncGenerator[dict, None]) -> AsyncGenerator[str, None]:
    async for event in r:
        yield json.dumps(event, ensure_ascii=False) + "\n"


@bp.route("/chat_stream", methods=["POST"])
async def chat_stream():
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    approach = request_json["approach"]
    try:
        impl = current_app.config[CONFIG_CHAT_APPROACHES].get(approach)
        if not impl:
            return jsonify({"error": "unknown approach"}), 400
        response_generator = impl.run_with_streaming(request_json["history"], request_json.get("overrides", {}))
        response = await make_response(format_as_ndjson(response_generator))
        response.timeout = None  # type: ignore
        return response
    except Exception as e:
        logging.exception("Exception in /chat")
        return jsonify({"error": str(e)}), 500


@bp.before_app_serving
async def setup_clients():
    # Replace these with your own values, either in environment variables or directly here
    AZURE_STORAGE_ACCOUNT = os.environ["AZURE_STORAGE_ACCOUNT"]
    AZURE_STORAGE_CONTAINER = os.environ["AZURE_STORAGE_CONTAINER"]
    AZURE_STORAGE_DOCUMENT_CONTAINER = os.environ["AZURE_STORAGE_DOCUMENT_CONTAINER"]
    AZURE_SEARCH_SERVICE = os.environ["AZURE_SEARCH_SERVICE"]
    AZURE_SEARCH_INDEX = os.environ["AZURE_SEARCH_INDEX"]

    AZURE_STORAGE_ACCOUNT_KEY = os.environ["AZURE_STORAGE_ACCOUNT_KEY"]
    AZURE_SEARCH_SERVICE_KEY = os.environ["AZURE_SEARCH_SERVICE_KEY"]
    AZURE_FORMRECOGNIZER_SERVICE = os.environ["AZURE_FORMRECOGNIZER_SERVICE"]
    AZURE_FORMRECOGNIZER_KEY = os.environ["AZURE_FORMRECOGNIZER_KEY"]
    # Shared by all OpenAI deployments
    OPENAI_HOST = os.getenv("OPENAI_HOST", "azure")
    OPENAI_CHATGPT_MODEL = os.environ["AZURE_OPENAI_CHATGPT_MODEL"]
    OPENAI_EMB_MODEL = os.getenv("AZURE_OPENAI_EMB_MODEL_NAME", "text-embedding-ada-002")
    # Used with Azure OpenAI deployments
    AZURE_OPENAI_KEY = os.environ["AZURE_OPENAI_KEY"]
    AZURE_OPENAI_SERVICE = os.getenv("AZURE_OPENAI_SERVICE")
    AZURE_OPENAI_CHATGPT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHATGPT_DEPLOYMENT")
    AZURE_OPENAI_EMB_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMB_DEPLOYMENT")
    # Used only with non-Azure OpenAI deployments
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_ORGANIZATION = os.getenv("OPENAI_ORGANIZATION")

    KB_FIELDS_CONTENT = os.getenv("KB_FIELDS_CONTENT", "content")
    KB_FIELDS_SOURCEPAGE = os.getenv("KB_FIELDS_SOURCEPAGE", "sourcepage")

    # Use the current user identity to authenticate with Azure OpenAI, Cognitive Search and Blob Storage (no secrets needed,
    # just use 'az login' locally, and managed identity when deployed on Azure). If you need to use keys, use separate AzureKeyCredential instances with the
    # keys for each service
    # If you encounter a blocking error during a DefaultAzureCredential resolution, you can exclude the problematic credential by using a parameter (ex. exclude_shared_token_cache_credential=True)

    # Set up clients for Cognitive Search and Storage
    search_index_client = SearchIndexClient(
        endpoint=f"https://{AZURE_SEARCH_SERVICE}.search.windows.net/",
        credential=AzureKeyCredential(AZURE_SEARCH_SERVICE_KEY),
    )
    blob_client = BlobServiceClient(
        account_url=f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net", credential=AZURE_STORAGE_ACCOUNT_KEY
    )
    blob_container_client = blob_client.get_container_client(AZURE_STORAGE_CONTAINER)
    blob_document_container_client = blob_client.get_container_client(AZURE_STORAGE_DOCUMENT_CONTAINER)
    form_recognizer_client = DocumentAnalysisClient(
        endpoint=f"https://{AZURE_FORMRECOGNIZER_SERVICE}.cognitiveservices.azure.com/",
        credential=AzureKeyCredential(AZURE_FORMRECOGNIZER_KEY),
        headers={"x-ms-useragent": "azure-search-chat-demo/1.0.0"},
    )
    # Used by the OpenAI SDK
    if OPENAI_HOST == "azure":
        openai.api_base = f"https://{AZURE_OPENAI_SERVICE}.openai.azure.com"
        openai.api_version = "2023-07-01-preview"
        openai.api_type = "azure"
        openai.api_key = AZURE_OPENAI_KEY
    else:
        openai.api_type = "openai"
        openai.api_key = OPENAI_API_KEY
        openai.organization = OPENAI_ORGANIZATION

    current_app.config[CONFIG_SEARCH_INDEX] = AZURE_SEARCH_INDEX
    current_app.config[CONFIG_SEARCH_INDEX_CLIENT] = search_index_client
    current_app.config[CONFIG_BLOB_CONTAINER_CLIENT] = blob_container_client
    current_app.config[CONFIG_BLOB_DOCUMENT_CONTAINER_CLIENT] = blob_document_container_client
    current_app.config[CONFIG_FORM_RECOGNIZER_CLIENT] = form_recognizer_client
    current_app.config[CONFIG_OPENAI_HOST] = OPENAI_HOST
    current_app.config[CONFIG_EMBEDDING_MODEL] = OPENAI_EMB_MODEL
    current_app.config[CONFIG_AZURE_OPENAI_EMB_DEPLOYMENT] = AZURE_OPENAI_EMB_DEPLOYMENT
    all_files = await get_all_files(blob_document_container_client)
    ingest_json = await get_ingest_json(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT])
    for file in all_files:
        if file not in ingest_json:
            ingest_json[file] = {"status": 2}
    await set_ingest_json(current_app.config[CONFIG_BLOB_CONTAINER_CLIENT], ingest_json)
    if AZURE_SEARCH_INDEX not in search_index_client.list_index_names():
        search_index = SearchIndex(
            name=AZURE_SEARCH_INDEX,
            fields=INDEX_FIELDS,
            semantic_settings=SemanticSettings(
                configurations=[
                    SemanticConfiguration(
                        name="default",
                        prioritized_fields=PrioritizedFields(
                            title_field=None, prioritized_content_fields=[SemanticField(field_name="content")]
                        ),
                    )
                ]
            ),
            vector_search=VectorSearch(
                algorithm_configurations=[
                    VectorSearchAlgorithmConfiguration(
                        name="default", kind="hnsw", hnsw_parameters=HnswParameters(metric="cosine")
                    )
                ]
            ),
        )
        print(f"Creating {AZURE_SEARCH_INDEX} search index")
        search_index_client.create_index(search_index)
    else:
        print(f"Search index {AZURE_SEARCH_INDEX} already exists")
    search_client = SearchClient(
        endpoint=f"https://{AZURE_SEARCH_SERVICE}.search.windows.net",
        index_name=AZURE_SEARCH_INDEX,
        credential=AzureKeyCredential(AZURE_SEARCH_SERVICE_KEY),
    )
    current_app.config[CONFIG_SEARCH_CLIENT] = search_client

    # Various approaches to integrate GPT and external knowledge, most applications will use a single one of these patterns
    # or some derivative, here we include several for exploration purposes
    current_app.config[CONFIG_ASK_APPROACHES] = {
        "rtr": RetrieveThenReadApproach(
            search_client,
            OPENAI_HOST,
            AZURE_OPENAI_CHATGPT_DEPLOYMENT,
            OPENAI_CHATGPT_MODEL,
            AZURE_OPENAI_EMB_DEPLOYMENT,
            OPENAI_EMB_MODEL,
            KB_FIELDS_SOURCEPAGE,
            KB_FIELDS_CONTENT,
        ),
        "rrr": ReadRetrieveReadApproach(
            search_client,
            OPENAI_HOST,
            AZURE_OPENAI_CHATGPT_DEPLOYMENT,
            OPENAI_CHATGPT_MODEL,
            AZURE_OPENAI_EMB_DEPLOYMENT,
            OPENAI_EMB_MODEL,
            KB_FIELDS_SOURCEPAGE,
            KB_FIELDS_CONTENT,
        ),
        "rda": ReadDecomposeAsk(
            search_client,
            OPENAI_HOST,
            AZURE_OPENAI_CHATGPT_DEPLOYMENT,
            OPENAI_CHATGPT_MODEL,
            AZURE_OPENAI_EMB_DEPLOYMENT,
            OPENAI_EMB_MODEL,
            KB_FIELDS_SOURCEPAGE,
            KB_FIELDS_CONTENT,
        ),
    }
    current_app.config[CONFIG_CHAT_APPROACHES] = {
        "rrr": ChatReadRetrieveReadApproach(
            search_client,
            OPENAI_HOST,
            AZURE_OPENAI_CHATGPT_DEPLOYMENT,
            OPENAI_CHATGPT_MODEL,
            AZURE_OPENAI_EMB_DEPLOYMENT,
            OPENAI_EMB_MODEL,
            KB_FIELDS_SOURCEPAGE,
            KB_FIELDS_CONTENT,
        )
    }


def create_app():
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        configure_azure_monitor()
        AioHttpClientInstrumentor().instrument()
    app = Quart(__name__)
    max_mb_upload = 200
    app.config["MAX_CONTENT_LENGTH"] = max_mb_upload * 1000 * 1024
    app.register_blueprint(bp)
    app.asgi_app = OpenTelemetryMiddleware(app.asgi_app)
    # Level should be one of https://docs.python.org/3/library/logging.html#logging-levels
    logging.basicConfig(level=os.getenv("APP_LOG_LEVEL", "ERROR"))
    return app
