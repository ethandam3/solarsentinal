/**
 * config.js
 * Paste the CDK stack outputs here after `cdk deploy`.
 * The Outputs tab will show all three values.
 */

// From CDK Output: WebSocketUrl
export const WS_URL = import.meta.env.VITE_WS_URL || 'wss://vkm9pygam8.execute-api.us-east-1.amazonaws.com/prod'

// From CDK Output: RestApiUrl
export const REST_URL = import.meta.env.VITE_REST_URL || 'https://8diq28ge23.execute-api.us-east-1.amazonaws.com/prod'
