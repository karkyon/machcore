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

export type NcDetail = {
  id: number;
  partId: number;
  processL: number;
  machineId: number | null;
  machiningTime: number | null;
  setupTimeRef: number | null;
  folderName: string;
  fileName: string;
  oNumber: string | null;
  clampNote: string | null;
  version: string;
  status: string;
  registeredAt: string | null;
  approvedAt: string | null;
  registrar: { id: number; name: string } | null;
  approver: { id: number; name: string } | null;
  part: { partId: string; drawingNo: string; partName: string; clientName: string | null };
  machine: { code: string; name: string } | null;
};

export type NcTool = {
  id: number;
  sortOrder: number;
  processType: string | null;
  chipModel: string | null;
  holderModel: string | null;
  noseR: string | null;
  tNumber: string | null;
  note: string | null;
};

export type ChangeHistory = {
  id: number;
  changed_at: string;
  change_type: string;
  operator_name: string | null;
  ver_before: string | null;
  ver_after: string | null;
  change_detail: string | null;
};

export type WorkRecord = {
  id: number;
  work_date: string;
  operator_name: string | null;
  machine_code: string | null;
  setup_time: number | null;
  machining_time: number | null;
  quantity: number | null;
  note: string | null;
};

export type SetupSheetLog = {
  id: number;
  printed_at: string;
  printer_name: string | null;
  version: string | null;
};

export const ncApi = {
  search: (key: string, q: string) =>
    api.get<{ total: number; data: NcSearchResult[] }>("/nc/search", {
      params: { key, q, limit: 100 },
    }),
  recent: () => api.get<RecentAccess[]>("/nc/recent"),
  findOne: (nc_id: number) => api.get<NcDetail>(`/nc/${nc_id}`),
  changeHistory: (nc_id: number) => api.get<ChangeHistory[]>(`/nc/${nc_id}/change-history`),
  workRecords: (nc_id: number) => api.get<WorkRecord[]>(`/nc/${nc_id}/work-records`),
  setupSheetLogs: (nc_id: number) => api.get<SetupSheetLog[]>(`/nc/${nc_id}/setup-sheet-logs`),
};

export type UserInfo = {
  id: number;
  name: string;
  role: "OPERATOR" | "ADMIN";
  avatarPath: string | null;
  isActive: boolean;
};

export type WorkSessionResponse = {
  access_token: string;
  session_type: string;
  operator: { id: number; name: string; role: string };
  expires_at: string;
};

export const usersApi = {
  list: () => api.get<UserInfo[]>("/users"),
};

export const authApi = {
  createWorkSession: (body: {
    operator_id: number;
    password: string;
    session_type: string;
  }) => api.post<WorkSessionResponse>("/auth/work-session", body),

  endWorkSession: (token: string) =>
    api.delete("/auth/work-session", {
      headers: { Authorization: `Bearer ${token}` },
    }),
};
