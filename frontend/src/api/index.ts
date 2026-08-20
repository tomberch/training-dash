/**
 * API module index - re-exports all API functions and types.
 *
 * Import from '@/api' or '@/api.ts' (the latter re-exports this for backward compatibility).
 */

// Base utilities and error types
export { API_BASE, ApiError, extractError, apiGet, apiPost, apiPut, apiPatch, apiDelete } from "./base";

// Shared types
export type {
  PeakPower,
  Activity,
  ActivityType,
  PaginationMeta,
  PaginatedActivities,
  GeoJSONFeature,
  GeoJSONFeatureCollection,
  PRValue,
  Records,
  RoutePR,
  RoutePRsPage,
  RecordsResponse,
  GapPoint,
  CompareResponse,
  SameRouteResponse,
  WbalPoint,
  WbalResponse,
  JobStatus,
} from "./types";
export { ACTIVITY_TYPES, ACTIVITY_TYPE_LABELS } from "./types";

// Activities API
export type {
  FitDevice,
  FitDevicesResponse,
  UploadToProviderRequest,
  UploadToProviderResponse,
} from "./activities";
export {
  fetchActivities,
  fetchActivity,
  fetchActivityRecords,
  fetchActivityWbal,
  fetchSameRouteActivities,
  updateActivityTitle,
  updateActivityType,
  generateActivityTitle,
  deleteActivity,
  fetchComparison,
  uploadFit,
  fetchJobStatus,
  fetchFitDevices,
  uploadToProvider,
} from "./activities";

// Auth API
export { login, register, logout } from "./auth";

// User API
export type {
  HrPowerModelStatus,
  User,
  Notification,
  NotificationsResponse,
  RecalculationJob,
  OAuthLink,
} from "./user";
export {
  fetchMe,
  updatePreferences,
  fetchNotifications,
  acceptNotification,
  dismissNotification,
  dismissAllNotifications,
  createNotification,
  uploadAvatar,
  deleteAvatar,
  triggerGarminSync,
  triggerXertSync,
  triggerRecalculation,
  fetchRecalculationStatus,
  fetchOAuthLinks,
  disconnectOAuthProvider,
  setPassword,
  hasPassword,
} from "./user";

// Athlete API
export type {
  ThresholdEntry,
  CreateThresholdRequest,
  PowerZone,
  HrZone,
  ZonesResponse,
  ZoneUpdate,
  UpdateZonesRequest,
  MetricEntryResponse,
  MetricEntryCreate,
  MetricEntryUpdate,
  CurrentMetricsResponse,
} from "./athlete";
export {
  fetchThresholds,
  createThreshold,
  fetchZones,
  updateZones,
  fetchMetrics,
  createMetric,
  updateMetric,
  deleteMetric,
  fetchCurrentMetrics,
  fetchEffectiveMetrics,
} from "./athlete";

// Integrations API
export type {
  XertCredentialsStatus,
  GarminCredentialsStatus,
  GarminSaveResponse,
} from "./integrations";
export {
  fetchMyXertCredentials,
  saveMyXertCredentials,
  deleteMyXertCredentials,
  updateXertSyncEnabled,
  fetchMyGarminCredentials,
  saveMyGarminCredentials,
  completeGarminMfa,
  deleteMyGarminCredentials,
  updateGarminSyncEnabled,
} from "./integrations";

// Analytics API
export type {
  PMCPoint,
  PowerCurvePoint,
  FitnessSnapshot,
  FitnessResponse,
} from "./analytics";
export {
  fetchRecords,
  fetchPMC,
  fetchPowerCurve,
  fetchFitness,
} from "./analytics";

// Admin API
export type {
  AdminUser,
  AdminSettings,
  NukePreview,
  SystemEvent,
  SystemEventsResponse,
  SystemEventsFilters,
  ActiveJob,
  ActiveJobsResponse,
  CacheTypeStats,
  CacheHistoryEntry,
  CacheSizes,
  CacheStatsResponse,
} from "./admin";
export {
  fetchAdminUsers,
  fetchPendingUsers,
  createUser,
  approveUser,
  rejectUser,
  resetUserPassword,
  triggerUserSync,
  fetchAdminSettings,
  updateAdminSetting,
  fetchNukePreview,
  nukeActivities,
  nukeIntegrations,
  nukeAccount,
  fetchSystemEvents,
  fetchActiveJobs,
  fetchCacheStats,
} from "./admin";

// Query DSL API
export type {
  QueryErrorDetail,
  ListQueryResponse,
  ScalarQueryResponse,
  GroupedQueryResponse,
  QueryResponse,
  SavedFilter,
  SavedFilterListResponse,
  CreateSavedFilterRequest,
  UpdateSavedFilterRequest,
} from "./query";
export {
  QueryError,
  executeQuery,
  fetchSavedFilters,
  fetchDefaultFilter,
  fetchSavedFilter,
  createSavedFilter,
  updateSavedFilter,
  deleteSavedFilter,
  setDefaultFilter,
  clearDefaultFilter,
} from "./query";

// Events API
export type {
  RideEvent,
  JournalEntry,
  EventMedia,
  EventLink,
  JournalEntryActivity,
  EventStats,
  EventDetail,
  PaginatedEvents,
  CreateEventRequest,
  UpdateEventRequest,
  CreateJournalEntryRequest,
  UpdateJournalEntryRequest,
  CreateLinkRequest,
  CreateVideoRequest,
  AvailableActivity,
  AvailableEvent,
} from "./events";
export {
  fetchEvents,
  fetchEvent,
  createEvent,
  updateEvent,
  deleteEvent,
  createJournalEntry,
  updateJournalEntry,
  deleteJournalEntry,
  createEventLink,
  createEntryLink,
  deleteLink,
  createEventVideo,
  createEntryVideo,
  deleteEventVideo,
  deleteEntryVideo,
  uploadEventPhoto,
  uploadEntryPhoto,
  uploadEventPhotosBatch,
  deleteMedia,
  setEventCover,
  removeEventCover,
  fetchAvailableActivities,
  batchLinkActivities,
  unlinkActivityFromEvent,
  linkActivityToEntry,
  unlinkActivityFromEntry,
  fetchAvailableEventsForActivity,
  quickLinkActivityToEvent,
} from "./events";
