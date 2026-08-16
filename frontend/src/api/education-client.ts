import type { ApiTransport } from "./http";
import type {
  CourseEnrollmentCreate,
  CourseEnrollmentCreated,
  EducationAttendance,
  EducationAttendanceWrite,
  EducationGroup,
  EducationGroupWrite,
  EducationPaymentControl,
  EducationPaymentCreate,
  EducationPaymentMonth,
  EducationPayroll,
  EducationPayrollCreate,
  EducationStatisticsPeriod,
  EducationStatisticsReport,
  EducationStudent,
  EducationStudentCard,
  EducationStudentWrite,
  EducationTeacher,
  EducationTeacherWrite,
  StatisticsPeriod,
} from "./types";

export function createEducationClient(transport: ApiTransport) {
  const request = transport.request.bind(transport);

  return {
    createCourseEnrollment(
      body: CourseEnrollmentCreate,
    ): Promise<CourseEnrollmentCreated> {
      return request("POST", "/api/v1/education/enrollments", body, true);
    },

    getEducationStatistics(
      period: EducationStatisticsPeriod = "month",
      selectedDate = "",
    ): Promise<EducationStatisticsReport> {
      const query = new URLSearchParams({ period });
      if (selectedDate) query.set("date", selectedDate);
      return request(
        "GET",
        `/api/v1/education/statistics?${query.toString()}`,
        undefined,
        true,
      );
    },

    getEducationGroups(): Promise<EducationGroup[]> {
      return request("GET", "/api/v1/education/groups", undefined, true);
    },

    createEducationGroup(body: EducationGroupWrite): Promise<{ ok: true; id: number }> {
      return request("POST", "/api/v1/education/groups", body, true);
    },

    updateEducationGroup(
      groupId: number,
      body: EducationGroupWrite,
    ): Promise<{ ok: true }> {
      return request("PUT", `/api/v1/education/groups/${groupId}`, body, true);
    },

    deleteEducationGroup(groupId: number): Promise<void> {
      return request("DELETE", `/api/v1/education/groups/${groupId}`, undefined, true);
    },

    getEducationStudents(groupId = 0): Promise<EducationStudent[]> {
      const query = new URLSearchParams({ group_id: String(groupId) });
      return request(
        "GET",
        `/api/v1/education/students?${query.toString()}`,
        undefined,
        true,
      );
    },

    createEducationStudent(
      body: EducationStudentWrite,
    ): Promise<{ ok: true; id: number }> {
      return request("POST", "/api/v1/education/students", body, true);
    },

    updateEducationStudent(
      studentId: number,
      body: EducationStudentWrite,
    ): Promise<{ ok: true }> {
      return request("PUT", `/api/v1/education/students/${studentId}`, body, true);
    },

    deleteEducationStudent(studentId: number): Promise<void> {
      return request(
        "DELETE",
        `/api/v1/education/students/${studentId}`,
        undefined,
        true,
      );
    },

    getEducationStudentCard(studentId: number): Promise<EducationStudentCard> {
      return request(
        "GET",
        `/api/v1/education/students/${studentId}/card`,
        undefined,
        true,
      );
    },

    transferEducationStudent(
      studentId: number,
      body: { group_id: number; transfer_date: string; note: string },
    ): Promise<{ ok: true; group_id: number; group_name: string }> {
      return request(
        "POST",
        `/api/v1/education/students/${studentId}/transfer`,
        body,
        true,
      );
    },

    getEducationAttendance(
      groupId: number,
      lessonDate: string,
    ): Promise<EducationAttendance> {
      const query = new URLSearchParams({
        group_id: String(groupId),
        lesson_date: lessonDate,
      });
      return request(
        "GET",
        `/api/v1/education/attendance?${query.toString()}`,
        undefined,
        true,
      );
    },

    saveEducationAttendance(
      body: EducationAttendanceWrite,
    ): Promise<{ ok: true; saved: number }> {
      return request("PUT", "/api/v1/education/attendance", body, true);
    },

    getEducationPaymentControl(groupId = 0): Promise<EducationPaymentControl> {
      const query = new URLSearchParams({ group_id: String(groupId) });
      return request(
        "GET",
        `/api/v1/education/payment-control?${query.toString()}`,
        undefined,
        true,
      );
    },

    getEducationPayments(
      paymentMonth: string,
      groupId = 0,
    ): Promise<EducationPaymentMonth> {
      const query = new URLSearchParams({
        payment_month: paymentMonth,
        group_id: String(groupId),
      });
      return request(
        "GET",
        `/api/v1/education/payments?${query.toString()}`,
        undefined,
        true,
      );
    },

    createEducationPayment(
      body: EducationPaymentCreate,
    ): Promise<{ ok: true; id: number; receipt_no: number }> {
      return request("POST", "/api/v1/education/payments", body, true);
    },

    voidEducationPayment(
      paymentId: number,
      reason: string,
    ): Promise<{ ok: true; voided: true }> {
      return request(
        "POST",
        `/api/v1/education/payments/${paymentId}/void`,
        { reason },
        true,
      );
    },

    getEducationTeachers(): Promise<EducationTeacher[]> {
      return request("GET", "/api/v1/education/teachers", undefined, true);
    },

    createEducationTeacher(
      body: EducationTeacherWrite,
    ): Promise<{ ok: true; id: number }> {
      return request("POST", "/api/v1/education/teachers", body, true);
    },

    updateEducationTeacher(
      teacherId: number,
      body: EducationTeacherWrite,
    ): Promise<{ ok: true }> {
      return request("PUT", `/api/v1/education/teachers/${teacherId}`, body, true);
    },

    deleteEducationTeacher(teacherId: number): Promise<void> {
      return request(
        "DELETE",
        `/api/v1/education/teachers/${teacherId}`,
        undefined,
        true,
      );
    },

    getEducationPayroll(paymentMonth: string): Promise<EducationPayroll> {
      const query = new URLSearchParams({ payment_month: paymentMonth });
      return request(
        "GET",
        `/api/v1/education/teacher-payroll?${query.toString()}`,
        undefined,
        true,
      );
    },

    createEducationPayroll(
      body: EducationPayrollCreate,
    ): Promise<{ ok: true; id: number }> {
      return request("POST", "/api/v1/education/teacher-payroll", body, true);
    },

    deleteEducationPayroll(paymentId: number): Promise<void> {
      return request(
        "DELETE",
        `/api/v1/education/teacher-payroll/${paymentId}`,
        undefined,
        true,
      );
    },
  };
}

export type EducationClient = ReturnType<typeof createEducationClient>;
