import React, { useEffect, useState, useRef, useContext } from "react";
import styles from "./Document.module.css";
import { PrimaryButton, TextField } from "@fluentui/react";
import PDFfile from "../../assets/pdf.svg";
import Pending from "../../assets/pending.svg";
import Verified from "../../assets/verified.svg";
import Loading from "../../assets/loading.svg";
import Loader from "../../assets/loader.svg";
import { ContextualMenu, ContextualMenuItemType, IContextualMenuItem } from "@fluentui/react/lib/ContextualMenu";
import Context from "../../context/store";
import { useNavigate } from "react-router-dom";
import { ArrowCounterclockwise24Filled } from "@fluentui/react-icons";

const FileGridItem = (props: any) => {
    const { document, ingested, handleUpdate, handleDelete, ingestLock } = props;
    const [showContextualMenu, setShowContextualMenu] = useState<boolean>(false);
    const [file, setFile] = useState();
    const onHideContextualMenu = () => setShowContextualMenu(false);

    const linkRef = useRef<HTMLInputElement>(null);
    const fileRef = useRef<HTMLInputElement>(null);
    const hrefRef = useRef<HTMLAnchorElement>(null);

    const onUpdateChange = (e: any) => {
        if (e.target.files) {
            handleUpdate(e.target.files[0]);
            setFile(undefined);
        }
    };
    const menuItems: IContextualMenuItem[] = [
        {
            key: "openItem",
            text: "Open",
            iconProps: { iconName: "Folder", style: { color: "salmon" } },
            onClick: () => hrefRef.current?.click()
        },
        {
            key: "divider_1",
            itemType: ContextualMenuItemType.Divider
        },
        {
            key: "updateItem",
            text: "Update",
            iconProps: { iconName: "Upload", style: { color: "blue" } },
            onClick: () => fileRef.current?.click(),
            disabled: ingestLock
        },
        {
            key: "deleteItem",
            text: "Delete",
            iconProps: { iconName: "Delete", style: { color: "red" } },
            onClick: handleDelete,
            disabled: ingestLock
        }
        // {
        //     key: "divider_1",
        //     itemType: ContextualMenuItemType.Divider
        // },
        // {
        //     key: "rename",
        //     text: "Rename",
        //     onClick: () => console.log("Rename clicked")
        // },
        // {
        //     key: "edit",
        //     text: "Edit",
        //     onClick: () => console.log("Edit clicked")
        // },
        // {
        //     key: "properties",
        //     text: "Properties",
        //     onClick: () => console.log("Properties clicked")
        // },
        // {
        //     key: "linkNoTarget",
        //     text: "Link same window",
        //     href: "http://bing.com"
        // },
        // {
        //     key: "linkWithTarget",
        //     text: "Link new window",
        //     href: "http://bing.com",
        //     target: "_blank"
        // },
        // {
        //     key: "linkWithOnClick",
        //     name: "Link click",
        //     href: "http://bing.com",
        //     onClick: ev => {
        //         alert("Link clicked");
        //         ev?.preventDefault();
        //     },
        //     target: "_blank"
        // },
        // {
        //     key: "disabled",
        //     text: "Disabled item",
        //     disabled: true,
        //     onClick: () => console.error("Disabled item should not be clickable.")
        // }
    ];
    if (ingested?.operation == 2) {
        return (
            <div className={styles.gridItem} style={{ position: "relative", opacity: 0.5, cursor: "not-allowed" }}>
                <div style={{ paddingBottom: "10px" }}>
                    <img src={PDFfile} alt="pdf file" height="50px" width="60px" />
                </div>
                <div>{document}</div>
                <div className={styles.ingestIndicator}>
                    {ingested?.status == 1 ? (
                        <img className={styles.rotating} src={Loading} alt="Loading" height="30px" width="30px" />
                    ) : (
                        <img src={Pending} alt="Pending" height="40px" width="40px" />
                    )}
                </div>
            </div>
        );
    }

    return (
        <div>
            <a ref={hrefRef} href={`/file/${document}`} target="_blank" style={{ display: "none" }} />
            <div
                ref={linkRef}
                className={styles.gridItem}
                onClick={() => hrefRef.current?.click()}
                onContextMenu={e => {
                    e.preventDefault();
                    setShowContextualMenu(true);
                }}
                style={{ position: "relative" }}
            >
                <div style={{ paddingBottom: "10px" }}>
                    <img src={PDFfile} alt="pdf file" height="50px" width="60px" />
                </div>
                <div>{document}</div>
                <div className={styles.ingestIndicator}>
                    {ingested?.status === 2 ? (
                        <img src={Verified} alt="Verified" height="30px" width="30px" />
                    ) : ingested?.status === 1 ? (
                        <img className={styles.rotating} src={Loading} alt="Loading" height="30px" width="30px" />
                    ) : (
                        <img src={Pending} alt="Pending" height="40px" width="40px" />
                    )}
                </div>
            </div>
            <input ref={fileRef} type="file" style={{ display: "none" }} accept="application/pdf" onChange={onUpdateChange} value={file} />
            <ContextualMenu
                items={menuItems}
                hidden={!showContextualMenu}
                target={linkRef}
                onItemClick={onHideContextualMenu}
                onDismiss={onHideContextualMenu}
            />
        </div>
    );
};

const parseJson = (resp: any) => {
    if (resp.status === 200) {
        return resp.json();
    }
    return resp.json().then((res: any) => {
        throw new Error(res.error);
    });
};
const handleError = (err: any) => console.log(err);

const Document = () => {
    const context = useContext(Context);
    const navigate = useNavigate();
    const [documents, setDocuments] = useState({ files: [], ingested: {}, ingest_lock: true });
    const [search, setSearch] = useState<string | undefined>("");
    const [file, setFile] = useState();
    const fileRef = useRef<HTMLInputElement>(null);

    const handleResponse = (resp: any) => setDocuments(resp);

    const fetchDocuments = () => {
        fetch("/files").then(parseJson).then(handleResponse).catch(handleError);
    };

    const handleUpload = (e: any) => {
        setFile(e.target.files);
        if (e.target.files) {
            const formData = new FormData();
            Object.keys(e.target.files).forEach(fileIndex => {
                formData.append("files", e.target.files[fileIndex], e.target.files[fileIndex].name);
            });
            fetch("/upload-files", {
                method: "POST",
                body: formData
            })
                .then(parseJson)
                .then(handleResponse)
                .catch(handleError);
            setFile(undefined);
        }
    };

    const handleUpdate = (file: any, document: string) => {
        const formData = new FormData();
        formData.append("files", file, document);
        fetch("/update-file", {
            method: "POST",
            body: formData
        })
            .then(parseJson)
            .then(handleResponse)
            .catch(handleError);
    };

    const handleDelete = (filename: any) => {
        fetch("/delete-file", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ file: filename })
        })
            .then(parseJson)
            .then(handleResponse)
            .catch(handleError);
    };

    const handleIngest = () => {
        setDocuments({ ...documents, ingest_lock: true });
        fetch("/ingest-files").then(parseJson).then(handleResponse).catch(handleError);
    };

    useEffect(fetchDocuments, []);
    useEffect(() => {
        if (documents.ingest_lock) {
            const intervalCall = setInterval(fetchDocuments, 2000);
            return () => clearInterval(intervalCall);
        }
    }, [documents.ingest_lock]);

    if (context.user !== "admin") {
        navigate("/");
    }

    let filteredDocuments = documents.files;
    if (search) {
        const regexp = new RegExp(".*" + search.replace(/[-[\]{}()*+?.,\\^$|]/g, "\\$&") + ".*", "i");
        filteredDocuments = filteredDocuments.filter(f => regexp.test(f));
    }
    return (
        <>
            <div style={{ display: "flex" }}>
                <div style={{ flexGrow: 1 }}>
                    {documents.ingest_lock && (
                        <div style={{ display: "flex", alignItems: "center", paddingTop: "15px", paddingLeft: "10px" }}>
                            <img className={styles.rotating} src={Loader} alt="Loading" height="30px" width="30px" style={{ marginRight: "20px" }} /> Reindexing
                            Process is Ongoing...
                        </div>
                    )}
                </div>
                <div className={styles.buttonRow}>
                    <div style={{ marginRight: "20px", display: "flex", alignItems: "center", cursor: "pointer" }}>
                        <ArrowCounterclockwise24Filled style={{ color: "grey" }} onClick={fetchDocuments} />
                    </div>
                    <div style={{ marginRight: "20px" }}>
                        <TextField placeholder="Search" iconProps={{ iconName: "Search" }} value={search} onChange={(e, value) => setSearch(value)} />
                    </div>
                    <input ref={fileRef} type="file" style={{ display: "none" }} accept="application/pdf" multiple onChange={handleUpload} value={file} />
                    <PrimaryButton
                        text="Upload"
                        style={{ marginRight: "10px" }}
                        onClick={() => {
                            if (fileRef.current) fileRef.current.click();
                        }}
                        disabled={documents.ingest_lock}
                    />
                    <PrimaryButton text="Reindex" onClick={handleIngest} disabled={documents.ingest_lock} />
                </div>
            </div>
            <div style={{ padding: "5px 10px" }}>
                <div className={styles.gridContainer}>
                    {filteredDocuments.map(d => (
                        <FileGridItem
                            key={d}
                            document={d}
                            ingested={documents.ingested[d]}
                            ingestLock={documents.ingest_lock}
                            handleUpdate={(f: any) => handleUpdate(f, d)}
                            handleDelete={() => handleDelete(d)}
                        />
                    ))}
                </div>
            </div>
        </>
    );
};

export default Document;
