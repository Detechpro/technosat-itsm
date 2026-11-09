export type Role =
  | "super_admin" | "it_admin" | "technician" | "hr_admin" | "manager" | "asset_manager" | "employee";

export interface User {
  id: number;
  username: string;
  email: string;
  display_name: string;
  role: Role;
  role_label: string;
  is_global_admin: boolean;
  department: number | null;
  manager: number | null;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Ticket {
  number: string;
  title: string;
  description: string;
  category: string;
  category_label: string;
  priority: string;
  priority_label: string;
  status: string;
  status_label: string;
  requester: string;
  requester_name: string;
  assignee: string | null;
  assignee_name: string | null;
  department: string | null;
  due_date: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
  is_overdue: boolean;
}

export interface Comment {
  id: number;
  author: string;
  body: string;
  is_internal: boolean;
  created_at: string;
}

export interface Task {
  id: number;
  ticket: string;
  ticket_title: string;
  title: string;
  assignee: string | null;
  status: string;
  status_label: string;
  priority: string;
  due_date: string | null;
  completed_at: string | null;
  m365_action: string;
  result: string;
}

export interface Approval {
  id: number;
  ticket: string;
  ticket_title: string;
  requester: string;
  category: string;
  decision: string;
  comment: string;
  decided_at: string | null;
  created_at: string;
}

export interface Dashboard {
  total: number;
  open: number;
  in_progress: number;
  resolved: number;
  overdue: number;
  pending_approvals: number;
  my_open_tasks: number;
  by_category: { category: string; n: number }[];
  by_priority: { priority: string; n: number }[];
}

export interface Directory {
  id: number;
  display_name: string;
  role: Role;
  role_label: string;
}

export const STATUS_OPTIONS = [
  ["new", "New"], ["submitted", "Submitted"], ["assigned", "Assigned"], ["in_progress", "In progress"],
  ["waiting_for_user", "Waiting for user"], ["on_hold", "On hold"], ["resolved", "Resolved"], ["closed", "Closed"],
  ["cancelled", "Cancelled"],
] as const;

export const CATEGORY_OPTIONS = [
  ["email", "Email services"], ["equipment", "IT equipment"], ["support", "IT support"],
  ["network_security", "Network and security"], ["smtp", "SMTP services"], ["general", "General"],
] as const;

export const PRIORITY_OPTIONS = [["critical", "Critical"], ["high", "High"], ["medium", "Medium"], ["low", "Low"]] as const;
