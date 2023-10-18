import { Outlet, NavLink, Link, useNavigate, useLocation } from "react-router-dom";
import appConfig from "../../utils/EAAppConfig";
import styles from "./Layout.module.css";
import { useContext } from "react";
import Context from "../../context/store";
// import ALGLogo from "../../assets/alg jpeg logo.jpg";

const Layout = () => {
    const headerStyle = {
        backgroundColor: appConfig.Layout.Headercolor.value,
        color: "#f2f2f2"
    };
    const context = useContext(Context);
    const location = useLocation();
    const navigate = useNavigate();

    if (!context.user && location.pathname !== "/") {
        navigate("/");
    }

    return (
        <div className={styles.layout}>
            <div className="header" style={headerStyle} role={"banner"}>
                <div className={styles.headerContainer}>
                    <Link to="/" className={styles.headerTitleContainer}>
                        <h3 className={styles.headerTitle}>{appConfig.Layout.HeaderLeftText.value}</h3>
                    </Link>
                    <nav>
                        {context.user && (
                            <ul className={styles.headerNavList}>
                                <li>
                                    <NavLink to="/" className={({ isActive }) => (isActive ? styles.headerNavPageLinkActive : styles.headerNavPageLink)}>
                                        Chat
                                    </NavLink>
                                </li>
                                {context.user === "admin" && (
                                    <li className={styles.headerNavLeftMargin}>
                                        <NavLink
                                            to="/documents"
                                            className={({ isActive }) => (isActive ? styles.headerNavPageLinkActive : styles.headerNavPageLink)}
                                        >
                                            Documents
                                        </NavLink>
                                    </li>
                                )}
                            </ul>
                        )}
                    </nav>

                    <div className={styles.headerRightSection} style={{ display: "flex", alignItems: "center" }}>
                        <h4 className={styles.headerRightText}>{appConfig.Layout.HeaderRightText.value}</h4>
                        {/* <img src={ALGLogo} alt="alg logo" height="40px" width="60px" style={{ marginLeft: "10px" }} /> */}
                        {context.user && (
                            <h4
                                className={styles.headerRightText}
                                style={{ cursor: "pointer" }}
                                onClick={() => {
                                    localStorage.setItem("user", "");
                                    context.setUser("");
                                }}
                            >
                                Logout
                            </h4>
                        )}
                    </div>
                    {/* <h4 className={styles.headerRightText}>Azure OpenAI + Cognitive Search</h4> */}
                </div>
            </div>

            <Outlet />
        </div>
    );
};

export default Layout;
