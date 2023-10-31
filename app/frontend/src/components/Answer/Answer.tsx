import { useMemo } from "react";
import React, { useState } from "react";
import { Stack, IconButton } from "@fluentui/react";
import DOMPurify from "dompurify";
import clipboardCopy from "clipboard-copy";
// import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
// import { faCopy } from '@fortawesome/free-regular-svg-icons';

import styles from "./Answer.module.css";
import appConfig from "../../utils/EAAppConfig";
import { AskResponse, getCitationFilePath } from "../../api";
import { parseAnswerToHtml } from "./AnswerParser";
import { AnswerIcon } from "./AnswerIcon";

interface Props {
    answer: AskResponse;
    isSelected?: boolean;
    isStreaming: boolean;
    onCitationClicked: (filePath: string) => void;
    onThoughtProcessClicked: () => void;
    onSupportingContentClicked: () => void;
    onFollowupQuestionClicked?: (question: string) => void;
    showFollowupQuestions?: boolean;
}

export const Answer = ({
    answer,
    isSelected,
    isStreaming,
    onCitationClicked,
    onThoughtProcessClicked,
    onSupportingContentClicked,
    onFollowupQuestionClicked,
    showFollowupQuestions
}: Props) => {
    const parsedAnswer = useMemo(() => parseAnswerToHtml(answer.answer, isStreaming, onCitationClicked), [answer]);

    const [isCopied, setIsCopied] = useState(false);
    const [showCitations, setShowCitations] = useState(false);

    const sanitizedAnswerHtml = DOMPurify.sanitize(parsedAnswer.answerHtml);
    // const handleCopyToClipboard = async () => {
    //   try {
    //     await clipboardCopy(parsedAnswer.answerHtml);
    //     setIsCopied(true);

    //   } catch (error) {
    //     console.error('Failed to copy to clipboard', error);

    //   }
    // };

    function stripHtmlTags(html: string) {
        const div = document.createElement("div");
        div.innerHTML = html;

        // Remove specific elements and content by selecting them and setting innerHTML to an empty string
        div.querySelectorAll(".supContainer").forEach(element => {
            element.innerHTML = "";
        });

        return div.textContent || div.innerText || "";
    }
    const handleCheckboxChange = () => {
        setShowCitations(!showCitations);
      };
    const handleCopyToClipboard = async () => {
        try {
            const textToCopy = stripHtmlTags(parsedAnswer.answerHtml);
            await clipboardCopy(textToCopy);
            setIsCopied(true); // Set the "Copied" state to true
            setTimeout(() => setIsCopied(false), 2000); // Reset it after 2 seconds
        } catch (error) {
            console.error("Failed to copy to clipboard", error);
        }
    };

    return (
        <Stack className={`${styles.answerContainer} ${isSelected && styles.selected}`} verticalAlign="space-between">
            <Stack.Item>
                <Stack horizontal horizontalAlign="space-between">
                    <AnswerIcon />
                    <div>
                        <IconButton
                            style={{ color: "black" }}
                            iconProps={{ iconName: "Lightbulb" }}
                            title="Show thought process"
                            ariaLabel="Show thought process"
                            onClick={() => onThoughtProcessClicked()}
                            disabled={!answer.thoughts}
                        />
                        <IconButton
                            style={{ color: "black" }}
                            iconProps={{ iconName: "ClipboardList" }}
                            title="Show supporting content"
                            ariaLabel="Show supporting content"
                            onClick={() => onSupportingContentClicked()}
                            disabled={!answer.data_points?.length}
                        />
                        {/* <button onClick={handleCopyToClipboard}>Copy to Clipboard</button> */}
                        {/* <FontAwesomeIcon
                            icon={faCopy}
                            title="Copy to Clipboard"
                            onClick={handleCopyToClipboard}
                            className={styles.copyToClipboardIcon} /> */}
                        <button
                            onClick={handleCopyToClipboard}
                            title={isCopied ? "Copied!" : "Copy to Clipboard"}
                            className={`${styles.copyToClipboardButton} ${isCopied && styles.copiedButton}`}
                        >
                            📋
                        </button>
                    </div>
                </Stack>
            </Stack.Item>

            <Stack.Item grow>
                <div className={styles.answerText} dangerouslySetInnerHTML={{ __html: sanitizedAnswerHtml }}>
                
                </div>
            </Stack.Item>
            <div className = {styles.showcitation}>
            <label>Show Citations</label>
            <input
               type="checkbox"
               checked={showCitations}
               onChange={handleCheckboxChange}/>
             
             </div>

            {showCitations && (
                <Stack.Item>
                    <Stack horizontal wrap tokens={{ childrenGap: 5 }}>
                        <span className={styles.citationLearnMore}>Citations:</span>
                        {parsedAnswer.citations.map((x, i) => {
                            const path = getCitationFilePath(x);
                            return (
                                <a key={i} className={styles.citation} title={x} onClick={() => onCitationClicked(path)}>
                                    {`${++i}. ${x}`}
                                </a>
                            );
                        })}
                    </Stack>
                </Stack.Item>
            )}

            {!!parsedAnswer.followupQuestions.length && showFollowupQuestions && onFollowupQuestionClicked && (
                <Stack.Item>
                    <Stack horizontal wrap className={`${!!parsedAnswer.citations.length ? styles.followupQuestionsList : ""}`} tokens={{ childrenGap: 6 }}>
                        <span className={styles.followupQuestionLearnMore}>Follow-up questions:</span>
                        {parsedAnswer.followupQuestions.map((x, i) => {
                            return (
                                <a key={i} className={styles.followupQuestion} title={x} onClick={() => onFollowupQuestionClicked(x)}>
                                    {`${x}`}
                                </a>
                            );
                        })}
                    </Stack>
                </Stack.Item>
            )}
        </Stack>
    );
};
