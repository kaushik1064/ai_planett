import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
    children?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null,
    };

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("Uncaught error:", error, errorInfo);
    }

    public render() {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen bg-neutral-900 text-white p-8 flex flex-col items-center justify-center font-sans">
                    <div className="max-w-2xl w-full bg-red-900/20 border border-red-500/50 rounded-xl p-6">
                        <h1 className="text-2xl font-bold text-red-400 mb-4">Something went wrong</h1>
                        <p className="mb-4 text-gray-300">The application crashed. Here is the error:</p>
                        <pre className="bg-black/50 p-4 rounded-lg overflow-auto text-sm font-mono text-red-200 whitespace-pre-wrap">
                            {this.state.error?.toString()}
                        </pre>
                        <button
                            onClick={() => window.location.reload()}
                            className="mt-6 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-white text-sm font-medium transition-colors"
                        >
                            Reload Page
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}
