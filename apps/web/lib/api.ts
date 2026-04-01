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

export type Status = "NEW" | "PENDING_APPROVAL" | "APPROVED" | "CHANGING";

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
  status: Status;
  processingId: string | null;
  drawingCount: number;
  photoCount: number;
  registeredAt: string;
  approvedAt: string | null;
  createdAt: string;
  updatedAt: string;
  registrar: { id: number; name: string };
  approver: { id: number; name: string } | null;
  part: {
    id: number;
    partId: string;
    drawingNo: string;
    name: string;
    clientName: string | null;
  };
  machine: {
    id: number;
    machineCode: string;
    machineName: string;
  } | null;
  tools: NcTool[];
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
  update: (nc_id: number, body: UpdateNcBody) => api.put<{ nc_id: number; message: string }>(`/nc/${nc_id}`, body),
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
    nc_program_id: number;
  }) => api.post<WorkSessionResponse>("/auth/work-session", body),

  endWorkSession: (token: string) =>
    api.delete("/auth/work-session", {
      headers: { Authorization: `Bearer ${token}` },
    }),
};
export type Machine = {
  id: number;
  machineCode: string;
  machineName: string;
  isActive: boolean;
};

export const machinesApi = {
  list: () => api.get<Machine[]>("/machines"),
};

export type WorkRecord = {
  id: number;
  work_date: string;
  operator_name: string | null;
  machine_code: string | null;
  setup_time: number | null;       // 分
  machining_time: number | null;   // 分
  cycle_time_sec: number | null;   // 秒
  quantity: number | null;
  interruption_time_min: number | null;
  work_type: string | null;
  note: string | null;
};
 
export type CreateWorkRecordBody = {
  setup_time_min?: number;
  machining_time_min?: number;
  cycle_time_sec?: number;
  quantity?: number;
  interruption_time_min?: number;
  work_type?: string;
  note?: string;
  machine_id?: number;
};

export const workRecordsApi = {
  list:   (ncId: number) => api.get<WorkRecord[]>(`/nc/${ncId}/work-records`),
  create: (ncId: number, body: CreateWorkRecordBody) =>
    api.post<{ id: number; message: string }>(`/nc/${ncId}/work-records`, body),
};

// ── ファイル管理 ────────────────────────────────────────────────
export type NcFile = {
  id: number;
  file_type: 'PHOTO' | 'DRAWING' | 'PROGRAM' | 'OTHER';
  original_name: string;
  stored_name: string;
  mime_type: string;
  file_size: number;
  file_path: string;
  thumbnail_path: string | null;
  uploaded_by: string | null;
  uploaded_at: string;
};

export const filesApi = {
  /** FIL-01: ファイル一覧 */
  list: (ncId: number) =>
    api.get<NcFile[]>(`/nc/${ncId}/files`),

  /** FIL-02: アップロード（multipart/form-data） */
  upload: (ncId: number, file: File, token: string) => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('nc_program_id', String(ncId));
    return api.post<{ id: number; message: string; stored_name: string }>(
      '/files/upload',
      fd,
      { headers: { Authorization: `Bearer ${token}` } },
    );
  },

  /** FIL-04: ファイル削除 */
  delete: (fileId: number, token: string) =>
    api.delete(`/files/${fileId}`, {
      headers: { Authorization: `Bearer ${token}` },
    }),
};

export type UpdateNcBody = {
  machine_id?: number;
  machining_time?: number;
  folder_name?: string;
  file_name?: string;
  version?: string;
  clamp_note?: string;
};

// ── 段取シート ──────────────────────────────────────────────────
export type PrintData = {
  id:           number;
  processL:     number;
  version:      string;
  status:       Status;
  folderName:   string;
  fileName:     string;
  oNumber:      string | null;
  machiningTime: number | null;
  clampNote:    string | null;
  part: {
    partId:     string;
    drawingNo:  string;
    name:       string;
    clientName: string | null;
  };
  machine: { machineCode: string; machineName: string } | null;
  registrar: { name: string };
  approver:  { name: string } | null;
  tools:     NcTool[];
};

export type PrintOptions = {
  include_tools?:    boolean;
  include_clamp?:    boolean;
  include_drawings?: boolean;
};

export const printApi = {
  getData: (ncId: number) =>
    api.get<PrintData>(`/nc/${ncId}/print-data`),
};