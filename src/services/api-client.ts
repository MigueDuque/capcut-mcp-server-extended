// API client for CapCut server communication

import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from 'axios';
import { API_BASE_URL } from '../constants.js';
import type { ApiResponse } from '../types.js';

export class CapCutApiClient {
  private client: AxiosInstance;

  constructor(baseURL: string = API_BASE_URL) {
    this.client = axios.create({
      baseURL,
      timeout: 60000, // 60 seconds timeout
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response) {
          // Server responded with error status
          const status = error.response.status;
          const data = error.response.data as any;
          
          if (status === 404) {
            throw new Error(`Resource not found: ${error.config?.url}`);
          } else if (status === 400) {
            throw new Error(`Bad request: ${data?.error || error.message}`);
          } else if (status === 500) {
            throw new Error(`Server error: ${data?.error || 'Internal server error'}`);
          } else if (status === 429) {
            throw new Error('Rate limit exceeded. Please try again later.');
          }
          
          throw new Error(data?.error || `API error (${status})`);
        } else if (error.request) {
          // Request made but no response
          throw new Error('CapCut API server is not responding. Please ensure the server is running.');
        } else {
          // Error setting up request
          throw new Error(`Request error: ${error.message}`);
        }
      }
    );
  }

  async request<T>(
    endpoint: string,
    method: 'GET' | 'POST' | 'PUT' | 'DELETE' = 'POST',
    data?: any,
    params?: Record<string, any>
  ): Promise<ApiResponse<T>> {
    try {
      const config: AxiosRequestConfig = {
        method,
        url: endpoint,
        ...(data && { data }),
        ...(params && { params }),
      };

      const response = await this.client.request<ApiResponse<T>>(config);
      return response.data;
    } catch (error) {
      if (error instanceof Error) {
        return {
          success: false,
          error: error.message
        };
      }
      return {
        success: false,
        error: 'Unknown error occurred'
      };
    }
  }

  // Specific API methods
  async createDraft(config: { width: number; height: number; fps?: number }) {
    return this.request('/create_draft', 'POST', config);
  }

  async addVideo(data: any) {
    return this.request('/add_video', 'POST', data);
  }

  async addAudio(data: any) {
    return this.request('/add_audio', 'POST', data);
  }

  async addText(data: any) {
    return this.request('/add_text', 'POST', data);
  }

  async addImage(data: any) {
    return this.request('/add_image', 'POST', data);
  }

  async addSubtitle(data: any) {
    return this.request('/add_subtitle', 'POST', data);
  }

  async addKeyframe(data: any) {
    return this.request('/add_keyframe', 'POST', data);
  }

  async addEffect(data: any) {
    return this.request('/add_effect', 'POST', data);
  }

  async addSticker(data: any) {
    return this.request('/add_sticker', 'POST', data);
  }

  async saveDraft(draftId: string) {
    return this.request('/save_draft', 'POST', { draft_id: draftId });
  }

  async getDuration(url: string) {
    return this.request('/get_duration', 'POST', { url });
  }
}

// Singleton instance
export const apiClient = new CapCutApiClient();
