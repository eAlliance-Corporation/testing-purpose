import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    build: {
        outDir: "../backend/static",
        emptyOutDir: true,
        sourcemap: true,
        rollupOptions: {
            output: {
                manualChunks: id => {
                    if (id.includes("@fluentui/react-icons")) {
                        return "fluentui-icons";
                    } else if (id.includes("@fluentui/react")) {
                        return "fluentui-react";
                    } else if (id.includes("node_modules")) {
                        return "vendor";
                    }
                }
            }
        }
    },
    server: {
        proxy: {
            "/ask": "http://localhost:50505",
            "/chat": "http://localhost:50505",
            "/file": "http://localhost:50505",
            "/files": "http://localhost:50505",
            "/content": "http://localhost:50505",
            "/upload-files": "http://localhost:50505",
            "/ingest-files": "http://localhost:50505",
            "/delete-file": "http://localhost:50505",
            "/update-file": "http://localhost:50505"
        }
    }
});
