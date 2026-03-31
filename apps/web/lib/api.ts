import axios from "axios";

const api = axios.create({ baseURL: "/api" });

export type NcSearchResult = {
  nc_id: number;
  part_db_id: number;
  part_id: string;
  drawing_no: string;
  part_name: string;
  client_name: string | null;
  process_l: number;
  machine_code: string | null;
  status: "NEW" | "PENDING_APPROVAL" | "APPROVED" | "CHANGING";
  version: string;
  folder_name: string;
  file_name: string;
  machining_time: number | null;
};

export type RecentAccess = {
  nc_id: number;
  drawing_no: string;
  part_name: string;
  process_l: number;
  machine_code: string | null;
  version: string;
  action_type: string;
  operator_name: string | null;
  accessed_at: string;
};

export const ncApi = {
  search: (key: string, q: string) =>
    api.get<{ total: number; data: NcSearchResult[] }>("/nc/search", {
      params: { key, q, limit: 100 },
    }),
  recent: () =>
    api.get<RecentAccess[]>("/nc/recent"),
};
