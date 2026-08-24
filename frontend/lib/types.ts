export type User = { id: number; username: string; name: string; role: string; organization: string; department?: string; crew?: string };
export type Project = { id: number; name: string; organization: string; address: string; status: string };
export type Location = { id: number; building: string; floor: string; zone: string };
export type Photo = { id: number; original_name: string; mime_type: string; size_bytes: number; content_url: string };
export type RecordItem = {
  id: number; project_id: number; category: string; description: string; occurred_at: string;
  latitude?: number; longitude?: number; gps_accuracy?: number; gps_captured_at?: string; gps_status: string;
  recorder: User; project: Project; location: Location; photos: Photo[]; created_at: string; updated_at: string;
};
export type TaskItem = {
  id: number; project_id: number; source_record_id?: number; title: string; description: string; due_at: string;
  status: string; creator: User; assignee: User; created_at: string; updated_at: string;
};
export type Dashboard = { today_records: number; pending_tasks: number; completed_tasks: number; recent_records: RecordItem[]; upcoming_tasks: TaskItem[] };

