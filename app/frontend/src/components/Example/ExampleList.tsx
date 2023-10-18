import { Example } from "./Example";

import styles from "./Example.module.css";
import appConfig from "../../utils/EAAppConfig";

export type ExampleModel = {
    text: string;
    value: string;
};

const questionsData = appConfig.Layout.Questions;
const EXAMPLES: ExampleModel[] = Object.keys(questionsData).map(key => ({
    text: questionsData[key as keyof typeof questionsData].value,
    value: questionsData[key as keyof typeof questionsData].value
}));

interface Props {
    onExampleClicked: (value: string) => void;
}

export const ExampleList = ({ onExampleClicked }: Props) => {
    return (
        <ul className={styles.examplesNavList}>
            {EXAMPLES.map((x, i) => (
                <li key={i}>
                    <Example text={x.text} value={x.value} onClick={onExampleClicked} />
                </li>
            ))}
        </ul>
    );
};
