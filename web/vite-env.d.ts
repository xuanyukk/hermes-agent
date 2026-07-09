/// <reference types="vite/client" />

declare namespace NodeJS {
  interface ProcessEnv {
    HERMES_DASHBOARD_URL?: string;
  }
}
