export type TaskStatus =
  | 'CREATED'
  | 'PLANNING'
  | 'RUNNING'
  | 'WAITING_APPROVAL'
  | 'VALIDATING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export type TaskRunner = 'opensandbox' | 'gemini-cli' | 'codex-cli' | 'claude-code' | 'agent-pipeline';

export interface Task {
  id: string;
  prompt: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
}

export interface TaskMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  task_id?: string;
  created_at: string;
}

export interface SessionRecord {
  id: string;
  task_id: string;
  sandbox_session_id: string | null;
  status: TaskStatus;
  created_at: string;
}

export interface TaskStartResponse {
  task: Task;
  session: {
    id: string;
    task_id: string;
    sandbox_session_id: string | null;
    status: TaskStatus;
    created_at: string;
  } | null;
  message: string;
  output?: {
    risk?: string;
    stdout?: string;
    stderr?: string;
    exit_code?: number;
    runner?: string;
    command?: string;
  };
}