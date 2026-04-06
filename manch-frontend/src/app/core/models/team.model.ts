export type TeamRole = 'owner' | 'admin' | 'member' | 'viewer';

export interface Team {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TeamMember {
  id: string;
  team_id: string;
  user_id: string;
  role: TeamRole;
  joined_at: string;
  email: string;
  full_name: string | null;
}

export interface TeamSummary {
  id: string;
  name: string;
  slug: string;
  role: TeamRole;
}
