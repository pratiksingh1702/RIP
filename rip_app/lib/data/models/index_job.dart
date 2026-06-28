import 'package:equatable/equatable.dart';
import '../../domain/enums/job_status.dart';

class IndexJob extends Equatable {
  final String jobId;
  final String? gitUrl;
  final String? projectName;
  final JobStatus status;
  final String progressMessage;
  final String? projectId;
  final int filesIndexed;
  final int entitiesFound;
  final String? error;

  const IndexJob({
    required this.jobId,
    this.gitUrl,
    this.projectName,
    required this.status,
    required this.progressMessage,
    this.projectId,
    this.filesIndexed = 0,
    this.entitiesFound = 0,
    this.error,
  });

  factory IndexJob.fromJson(Map<String, dynamic> json) {
    JobStatus status;
    try {
      status = JobStatus.values.firstWhere(
        (e) => e.name == (json['status'] as String?),
        orElse: () => JobStatus.pending,
      );
    } catch (e) {
      status = JobStatus.pending;
    }

    return IndexJob(
      jobId: json['job_id'] as String? ?? '',
      gitUrl: json['git_url'] as String?,
      projectName: json['project_name'] as String?,
      status: status,
      progressMessage: json['progress_message'] as String? ?? '',
      projectId: json['project_id'] as String?,
      filesIndexed: json['files_indexed'] as int? ?? 0,
      entitiesFound: json['entities_found'] as int? ?? 0,
      error: json['error'] as String?,
    );
  }

  @override
  List<Object?> get props => [
        jobId,
        gitUrl,
        projectName,
        status,
        progressMessage,
        projectId,
        filesIndexed,
        entitiesFound,
        error,
      ];
}
