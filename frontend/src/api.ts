import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface Rule {
  rule_id: string;
  keyword: string;
  dm_message: string;
  created_at: string;
}

export interface Delivery {
  delivery_id: string;
  rule_id: string;
  keyword: string;
  user_id: string;
  comment_id: string;
  status: 'pending' | 'queued' | 'sent' | 'delivered' | 'failed' | 'cancelled';
  attempts: number;
  external_dm_id?: string;
  last_error?: string;
  created_at: string;
  updated_at: string;
  delivered_at?: string;
}

export interface Stats {
  sent: number;
  failed: number;
  queued: number;
  duplicates_blocked: number;
}

export const apiService = {
  async createRule(keyword: string, dm_message: string): Promise<Rule> {
    const response = await api.post('/rules', { keyword, dm_message });
    return response.data;
  },

  async getRules(): Promise<Rule[]> {
    const response = await api.get('/rules');
    return response.data;
  },

  async getStats(): Promise<Stats> {
    const response = await api.get('/stats');
    return response.data;
  },

  async getDeliveries(): Promise<Delivery[]> {
    const response = await api.get('/deliveries');
    return response.data;
  },
};
