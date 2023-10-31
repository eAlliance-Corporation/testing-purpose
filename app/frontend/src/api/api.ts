import { AskRequest, AskResponse, ChatRequest } from "./models";
import { CosmosClient,PartitionKey } from '@azure/cosmos';

export async function askApi(options: AskRequest): Promise<AskResponse> {
    const response = await fetch("/ask", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            question: options.question,
            approach: options.approach,
            overrides: {
                retrieval_mode: options.overrides?.retrievalMode,
                semantic_ranker: options.overrides?.semanticRanker,
                semantic_captions: options.overrides?.semanticCaptions,
                top: options.overrides?.top,
                temperature: options.overrides?.temperature,
                prompt_template: options.overrides?.promptTemplate,
                prompt_template_prefix: options.overrides?.promptTemplatePrefix,
                prompt_template_suffix: options.overrides?.promptTemplateSuffix,
                exclude_category: options.overrides?.excludeCategory
            }
        })
    });

    const parsedResponse: AskResponse = await response.json();
    if (response.status > 299 || !response.ok) {
        throw Error(parsedResponse.error || "Unknown error");
    }

    saveQuestionAndAnswer(options.question, parsedResponse.answer);
    return parsedResponse;
}

const endpoint = 'https://history-c.documents.azure.com:443/';
const key = 'xy9CShbxmmkjlet45CyneUC2xg9f1rtro1oyWOC36f4ssB82uOfvWy6hFP69aQKPCPulYY9rjFrQACDbtDWU7g==';
const databaseId = 'ToDoList';
const containerId = 'history';

// Initialize the Cosmos DB client
const cosmosClient = new CosmosClient({ endpoint, key });


// Reference to your database and container
const database = cosmosClient.database(databaseId);
const container = database.container(containerId);

// Function to save a question and its generated answer to the Cosmos DB container
async function saveQuestionAndAnswer(question: string, answer: string) {
    try {
        const item = {
            id: generateUniqueId(), // Generate a unique ID for each question-answer pair
            question: question,
            answer: answer,
        };

        await container.items.create(item);
        console.log(item)
    } catch (error) {
        console.error('Error saving Question and Answer to Cosmos DB:', error);
    }
}

// Function to generate a unique ID for each question-answer pair (you can use your own logic)
function generateUniqueId() {
    return Date.now().toString(); // This is a simple example; you can use a more robust approach
}

export async function chatApi(options: ChatRequest): Promise<Response> {
    const url = options.shouldStream ? "/chat_stream" : "/chat";
    return await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            history: options.history,
            approach: options.approach,
            overrides: {
                retrieval_mode: options.overrides?.retrievalMode,
                semantic_ranker: options.overrides?.semanticRanker,
                semantic_captions: options.overrides?.semanticCaptions,
                top: options.overrides?.top,
                temperature: options.overrides?.temperature,
                prompt_template: options.overrides?.promptTemplate,
                prompt_template_prefix: options.overrides?.promptTemplatePrefix,
                prompt_template_suffix: options.overrides?.promptTemplateSuffix,
                exclude_category: options.overrides?.excludeCategory,
                suggest_followup_questions: options.overrides?.suggestFollowupQuestions
            }
        })
    });
}

export function getCitationFilePath(citation: string): string {
    return `/content/${citation}`;
}
