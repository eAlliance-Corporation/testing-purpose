import React, { useEffect, useState, useRef, useContext } from "react";
import styles from "./Document.module.css";

import { PrimaryButton, TextField } from "@fluentui/react";
import PDFfile from "../../assets/pdf.svg";
import Pending from "../../assets/pending.svg";
import Loading from "../../assets/loading.svg";
import Loader from "../../assets/loader.svg";
import Verified from "../../assets/verified.svg";
import { ContextualMenu, ContextualMenuItemType, IContextualMenuItem } from "@fluentui/react/lib/ContextualMenu";
import Context from "../../context/store";
import { useNavigate } from "react-router-dom";
import { ArrowCounterclockwise24Filled } from "@fluentui/react-icons";
import MainLoginPage from "./MainloginPage";


const FileGridItem = (props: any) => {
    const { document, ingested, handleUpdate, handleDelete, ingestLock,context } = props;
    const [showContextualMenu, setShowContextualMenu] = useState<boolean>(false);
    const [file, setFile] = useState();
    const navigate = useNavigate();
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
    const handleOpenDocument = () => {
        if (context.user === "admin") {
          // If the user is an admin, open the document
          hrefRef.current?.click();
        } else {
          // If the user is not an admin, redirect to the login page
          return <MainLoginPage />; // Replace "/login" with the actual login page route
        }
      };
    const menuItems: IContextualMenuItem[] = [
        {
            key: "openItem",
            text: "Open",
            iconProps: { iconName: "Folder", style: { color: "salmon" } },
            onClick: () => {
              if (context.user === "admin") {
                hrefRef.current?.click();
              } else {
                // If the user is not an admin, redirect to the login page
                navigate("/Mainloginpage"); // Replace "/login" with the actual login page route
              }
            }
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
    ];
    if (ingested?.operation == 2) {
        return (
            <div className={styles.listItem} >
                <img src={PDFfile} alt="pdf file" height="20px" width="20px" />
                <div style={{ marginLeft: "10px" }}>{document}</div> &nbsp;
                {ingested?.status == 1 ? (
                        <img className={styles.rotating} src={Loading} alt="Loading" height="20px" width="20px" />
                    ) : (
                        <img src={Pending} alt="Pending" height="20px" width="20px" />
                    )}
                </div>
                
                
           
        );
    }

    return (
      <li className={styles.listItem}>
        {/* <Route path="/file/:document"> */}
        {/* {context.user === "admin" ? ( */}
         <a ref={hrefRef} href={`/file/${document}`} target="_blank" onClick={handleOpenDocument}  >
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
                <img src={PDFfile} alt="pdf file" height="20px" width="20px" />
                <span>{document}</span>
                {ingested?.status === 2 ? (
                    <img src={Verified} alt="Verified" height="20px" width="20px" />
                ) : ingested?.status === 1 ? (
                    <img className={styles.rotating} src={Loading} alt="Loading" height="20px" width="20px" />
                ) : (
                    <img src={Pending} alt="Pending" height="20px" width="20px" />
                )}
            </div>
            </a>
            {/* ) : (
                <div>
                   <p>You do not have permission to access this document.</p>
                </div>
              )}
            </Route> */}
            <input
                ref={fileRef}
                type="file"
                style={{ display: "none" }}
                accept="application/pdf"
                onChange={onUpdateChange}
                value={file}
            />
            <ContextualMenu
                items={menuItems}
                hidden={!showContextualMenu}
                target={linkRef}
                onItemClick={onHideContextualMenu}
                onDismiss={onHideContextualMenu}
            />
        </li>
        
    );
};

const parseJson = (resp: any) => {
    if (resp.status === 200) {
        return resp.json();
    }
    return resp.json().then((res: any) => {
        throw  Error(res.error);
    });
};

const handleError = (err: any) => console.log(err);

const Document = () => {
    const context = useContext(Context);
    
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
        return <MainLoginPage />;
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
                        <img
                            className={styles.rotating}
                            src={Loader}
                            alt="Loading"
                            height="20px"
                            width="20px"
                            style={{ marginRight: "20px" }}
                        />{" "}
                        Reindexing Process is Ongoing...
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
            {/* <Route path="/documents"> */}
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
                            // context={context} // Pass 'context' as a prop
                        />
                    ))}
                </div>
            </div>
            {/* </Route> */}
        </>
    );
};

export default Document;
