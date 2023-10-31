import React, { useEffect } from "react";
import ReactDOM from "react-dom/client";
import { createHashRouter, RouterProvider } from "react-router-dom";
import { initializeIcons } from "@fluentui/react";
import appConfig from "./utils/EAAppConfig";

import "./index.css";


import { ContextProvider } from "./context/store";
import Layout from "./pages/layout/Layout";
import Chat from "./pages/chat/Chat";
import Document from "./pages/document/Document";


initializeIcons();
document.title = appConfig.Layout.applicationname.value;


const router = createHashRouter([
    {
        path: "/",
        element: <Layout />,
        children: [
            {
                index: true,
                element: <Chat />
            },
            {
                path: "/documents",
                element: <Document />
            },
            {
                path: "*",
                lazy: () => import("./pages/NoPage")
            }
        ]
    }
]);
// const App = () => {
//     useEffect(() => {
//         // Update the title dynamically here
//         document.title = appConfig.Layout.applicationname.value;
//     }, []); // The empty dependency array ensures this effect runs once


//     return <document.title />;
// };


// ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(<App />);


ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <React.StrictMode>
        <ContextProvider>
            <RouterProvider router={router} />
        </ContextProvider>
    </React.StrictMode>
);
