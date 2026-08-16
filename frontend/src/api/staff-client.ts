import type { ApiTransport } from "./http";
import type {
  StaffAccessWrite,
  StaffAttendance,
  StaffMember,
  StaffMemberWrite,
  StaffSchedule,
  StaffSetup,
} from "./types";

export function createStaffClient(transport: ApiTransport) {
  const request = transport.request.bind(transport);

  return {
    getStaffSetup(): Promise<StaffSetup> {
      return request("GET", "/api/v1/staff", undefined, true);
    },

    createStaffMember(body: StaffMemberWrite): Promise<StaffMember> {
      return request("POST", "/api/v1/staff", body, true);
    },

    updateStaffMember(
      staffId: number,
      body: Partial<StaffMemberWrite>,
    ): Promise<StaffMember> {
      return request("PUT", `/api/v1/staff/${staffId}`, body, true);
    },

    fireStaffMember(staffId: number): Promise<StaffMember> {
      return request("POST", `/api/v1/staff/${staffId}/fire`, undefined, true);
    },

    rehireStaffMember(staffId: number): Promise<StaffMember> {
      return request("POST", `/api/v1/staff/${staffId}/rehire`, undefined, true);
    },

    deleteStaffMember(staffId: number): Promise<void> {
      return request("DELETE", `/api/v1/staff/${staffId}`, undefined, true);
    },

    updateStaffAccess(staffId: number, body: StaffAccessWrite): Promise<StaffMember> {
      return request("PUT", `/api/v1/staff/${staffId}/access`, body, true);
    },

    updateStaffSchedule(
      staffId: number,
      schedule: StaffSchedule,
    ): Promise<StaffMember> {
      return request("PUT", `/api/v1/staff/${staffId}/schedule`, { schedule }, true);
    },

    createStaffProfession(name: string): Promise<{ professions: string[] }> {
      return request("POST", "/api/v1/staff/professions", { name }, true);
    },

    getStaffAttendance(day: string): Promise<StaffAttendance> {
      const query = new URLSearchParams({ day });
      return request(
        "GET",
        `/api/v1/staff/attendance?${query.toString()}`,
        undefined,
        true,
      );
    },

    updateStaffAttendance(
      staffId: number,
      body: { date: string; status: string; time_in: string; time_out: string },
    ): Promise<StaffAttendance> {
      return request("PUT", `/api/v1/staff/${staffId}/attendance`, body, true);
    },
  };
}

export type StaffClient = ReturnType<typeof createStaffClient>;
