import React, { useState, createContext } from "react";

const Context = createContext({
    user: localStorage.getItem("user") ?? "",
    setUser: (value: string) => {}
});

export const ContextProvider = (props: any) => {
    const [user, setUser] = useState(localStorage.getItem("user") ?? "");
    const context = {
        user,
        setUser
    };
    return <Context.Provider value={context}>{props.children}</Context.Provider>;
};

export default Context;
