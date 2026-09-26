import type { CourseEnrollmentTarget } from "../education/CourseEnrollment";
import type { MessagePeer } from "../messages/Messages";
import type { QueueBookingTarget } from "../queues/QueueBooking";

export type AuthIntent = {
  queue?: QueueBookingTarget;
  course?: CourseEnrollmentTarget;
  chat?: MessagePeer;
};
