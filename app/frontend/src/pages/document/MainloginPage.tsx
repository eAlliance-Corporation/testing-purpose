import { FontWeights, ITextFieldProps, ITheme, PrimaryButton, Text, TextField, getTheme, memoizeFunction } from "@fluentui/react";
import React, { useContext, useState } from "react";

import styles from "./Document.module.css";
import Context from "../../context/store";
// import ALGLogo from "../../assets/alg jpeg logo.jpg";

const MainLoginPage = () => {
    const context = useContext(Context);
    const [username, setUsername] = useState<string>("");
    const [password, setPassword] = useState<string>("");
    const [incorrectPassword, setIncorrectPassword] = useState<boolean>(false);

    const checkLogin = () => {
        if (username === "user" && password === "User@123") {
            localStorage.setItem("user", "user");
            context.setUser("user");
            setIncorrectPassword(false);
        } else if (username === "admin" && password === "Admin@123") {
            localStorage.setItem("user", "admin");
            context.setUser("admin");
            setIncorrectPassword(false);
        } else {
            setIncorrectPassword(true);
        }
    };

    const getDescriptionStyles = memoizeFunction((theme: ITheme) => ({
        root: { color: theme.palette.red, fontWeight: FontWeights.bold }
    }));

    const onRenderDescription = (props: ITextFieldProps | undefined): React.JSX.Element => {
        const theme = getTheme();
        return (
            <Text variant="small" styles={getDescriptionStyles(theme)}>
                {props?.description}
            </Text>
        );
    };
    const handleUsernameChange = (e: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>, value: string | undefined) => {
        if (value) setUsername(value);
    };
    const handlePasswordChange = (e: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>, value: string | undefined) => {
        if (value) setPassword(value);
    };

    return (
        <div className={styles.container}>
            <div className={styles.loginRow}>
                <div className={styles.loginBox}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                        {/* <img src={ALGLogo} alt="alg logo" height="150px" width="200px" /> */}
                    </div>
                    <TextField
                        className={styles.chatSettingsSeparator}
                        iconProps={{ iconName: "FollowUser", style: { color: "black" } }}
                        defaultValue={username}
                        label="Username"
                        onChange={handleUsernameChange}
                    />
                    <TextField
                        type="password"
                        className={styles.chatSettingsSeparator}
                        defaultValue={password}
                        label="Password"
                        description={incorrectPassword ? "Incorrect Password" : ""}
                        iconProps={{ iconName: "AzureKeyVault", style: { color: "black" } }}
                        onRenderDescription={onRenderDescription}
                        onChange={handlePasswordChange}
                    />
                    <div style={{ display: "flex", justifyContent: "right", paddingTop: "20px" }}>
                        <PrimaryButton text="Login" onClick={checkLogin} />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MainLoginPage;
