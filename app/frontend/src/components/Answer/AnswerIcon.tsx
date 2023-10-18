import { Sparkle28Filled } from "@fluentui/react-icons";
import appConfig from "../../utils/EAAppConfig";

export const AnswerIcon = () => {
    return <Sparkle28Filled primaryFill={appConfig.Layout.Headercolor.value} aria-hidden="true" aria-label="Answer logo" />;
};
