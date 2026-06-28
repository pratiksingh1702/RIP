import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/models/index_job.dart';
import 'connection_provider.dart';

class IndexJobsNotifier extends Notifier<Map<String, IndexJob>> {
  @override
  Map<String, IndexJob> build() {
    return {};
  }

  void addJob(IndexJob job) {
    state = {...state, job.jobId: job};
  }

  void updateJob(IndexJob job) {
    state = {...state, job.jobId: job};
  }

  void removeJob(String jobId) {
    final newState = Map<String, IndexJob>.from(state);
    newState.remove(jobId);
    state = newState;
  }
}

final indexJobsProvider = NotifierProvider<IndexJobsNotifier, Map<String, IndexJob>>(
  IndexJobsNotifier.new,
);
