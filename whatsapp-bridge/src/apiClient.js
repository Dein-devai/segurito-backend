const axios = require('axios');

/**
 * Cliente HTTP hacia el backend Python.
 */
class ApiClient {
  constructor() {
    const baseURL = process.env.BACKEND_URL || 'http://localhost:8000';
    const timeout = parseInt(process.env.BACKEND_TIMEOUT_MS, 10) || 35000;

    this._client = axios.create({ baseURL, timeout });
  }

  async chat(payload) {
    try {
      const resp = await this._client.post('/chat', payload);
      return resp.data;
    } catch (err) {
      if (err.response && err.response.status === 429) {
        const retryAfter = err.response.headers['retry-after'] || 5;
        console.log(`[ApiClient] Rate limited. Retrying in ${retryAfter}s...`);
        await new Promise((r) => setTimeout(r, retryAfter * 1000));
        const retry = await this._client.post('/chat', payload);
        return retry.data;
      }
      console.error('[ApiClient] Error calling /chat:', err.message);
      throw err;
    }
  }

  async health() {
    try {
      const resp = await this._client.get('/health');
      return resp.data;
    } catch (err) {
      console.error('[ApiClient] Backend health check failed:', err.message);
      return null;
    }
  }
}

module.exports = ApiClient;