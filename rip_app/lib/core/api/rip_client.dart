import 'package:dio/dio.dart';
import '../exceptions.dart';
import '../../data/models/project.dart';
import '../../data/models/search_result.dart';
import '../../data/models/index_job.dart';
import '../../utils/logger.dart';

class RipClient {
  late final Dio _dio;

  RipClient({required String serverUrl, String? apiKey}) {
    RipLogger.info('Initializing with serverUrl: $serverUrl', tag: 'RipClient');
    _dio = Dio(BaseOptions(
      baseUrl: serverUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: null,
      sendTimeout: null,
    ));

    if (apiKey != null && apiKey.isNotEmpty) {
      _dio.options.headers['Authorization'] = 'Bearer $apiKey';
      RipLogger.info('Added Authorization header', tag: 'RipClient');
    }

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        options.extra['startTime'] = DateTime.now();
        RipLogger.apiRequest(
          options.method,
          options.path,
          headers: options.headers,
          queryParameters: options.queryParameters,
          data: options.data,
        );
        handler.next(options);
      },
      onResponse: (response, handler) {
        final startTime = response.requestOptions.extra['startTime'] as DateTime?;
        final duration = startTime != null ? DateTime.now().difference(startTime) : null;

        RipLogger.apiResponse(
          response.statusCode,
          response.requestOptions.path,
          data: response.data,
          headers: response.headers.map,
          duration: duration,
        );
        handler.next(response);
      },
      onError: (error, handler) {
        RipLogger.error(
          'Dio Error: ${error.type} | Message: ${error.message}\n'
          '  Path: ${error.requestOptions.path}\n'
          '  Method: ${error.requestOptions.method}\n'
          '  Headers: ${error.requestOptions.headers}\n'
          '  QueryParams: ${error.requestOptions.queryParameters}\n'
          '  Payload: ${error.requestOptions.data}\n'
          '  Response Status: ${error.response?.statusCode}\n'
          '  Response Body: ${error.response?.data}',
          tag: 'RipClient_DioError',
          error: error,
        );
        if (error.response?.statusCode == 401) {
          throw RIPAuthException('Invalid or missing API key');
        } else if (error.response?.statusCode == 403) {
          throw RIPAuthException('Access denied: You do not have permission to access this project');
        } else if (error.response?.statusCode == 404) {
          throw RIPNotFoundException(error.message ?? 'Not found');
        } else if (error.type == DioExceptionType.connectionTimeout ||
            error.type == DioExceptionType.connectionError) {
          throw RIPConnectionException('Failed to connect to server');
        }
        handler.next(error);
      },
    ));
  }

  Future<List<Project>> listProjects({CancelToken? cancelToken}) async {
    try {
      RipLogger.info('Calling listProjects()', tag: 'RipClient_Endpoint');
      final response = await _dio.get('/projects/', cancelToken: cancelToken);
      final List<dynamic> data = response.data as List;
      final projects = data.map((j) => Project.fromJson(j as Map<String, dynamic>)).toList();
      RipLogger.success('listProjects() returned ${projects.length} projects', tag: 'RipClient_Endpoint');
      return projects;
    } catch (e, stack) {
      RipLogger.error('listProjects() failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<Project> getProject(String projectId) async {
    try {
      RipLogger.info('Calling getProject(projectId: $projectId)', tag: 'RipClient_Endpoint');
      final response = await _dio.get('/projects/$projectId');
      final project = Project.fromJson(response.data as Map<String, dynamic>);
      RipLogger.success('getProject(projectId: $projectId) succeeded: ${project.projectName}', tag: 'RipClient_Endpoint');
      return project;
    } catch (e, stack) {
      RipLogger.error('getProject(projectId: $projectId) failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<void> deleteProject(String projectId) async {
    try {
      RipLogger.info('Calling deleteProject(projectId: $projectId)', tag: 'RipClient_Endpoint');
      await _dio.delete('/projects/$projectId');
      RipLogger.success('deleteProject(projectId: $projectId) succeeded', tag: 'RipClient_Endpoint');
    } catch (e, stack) {
      RipLogger.error('deleteProject(projectId: $projectId) failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<IndexJob> startGitIndex({
    required String gitUrl,
    required String projectName,
    String branch = 'main',
    CancelToken? cancelToken,
  }) async {
    try {
      RipLogger.info('Calling startGitIndex(gitUrl: $gitUrl, projectName: $projectName, branch: $branch)', tag: 'RipClient_Endpoint');
      final response = await _dio.post('/git/index', data: {
        'git_url': gitUrl,
        'project_name': projectName,
        'branch': branch,
      }, cancelToken: cancelToken);
      final job = IndexJob.fromJson(response.data as Map<String, dynamic>);
      RipLogger.success('startGitIndex succeeded: job ${job.jobId} state ${job.status}', tag: 'RipClient_Endpoint');
      return job;
    } catch (e, stack) {
      RipLogger.error('startGitIndex failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<IndexJob> getJobStatus(String jobId) async {
    try {
      RipLogger.info('Calling getJobStatus(jobId: $jobId)', tag: 'RipClient_Endpoint');
      final response = await _dio.get('/git/status/$jobId');
      final job = IndexJob.fromJson(response.data as Map<String, dynamic>);
      RipLogger.success('getJobStatus(jobId: $jobId) status is ${job.status}', tag: 'RipClient_Endpoint');
      return job;
    } catch (e, stack) {
      RipLogger.error('getJobStatus(jobId: $jobId) failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<List<SearchResult>> search({
    required String projectId,
    required String query,
    int limit = 10,
    CancelToken? cancelToken,
  }) async {
    try {
      RipLogger.info('Calling search(projectId: $projectId, query: "$query", limit: $limit)', tag: 'RipClient_Endpoint');
      final response = await _dio.get(
        '/search',
        queryParameters: {
          'q': query,
          'project_id': projectId,
          'top': limit,
        },
        cancelToken: cancelToken,
      );
      final data = response.data as Map<String, dynamic>;
      final List<dynamic> results = data['data'] as List? ?? [];
      final list = results
          .map((r) => SearchResult.fromJson(r as Map<String, dynamic>))
          .toList();
      RipLogger.success('search returned ${list.length} results', tag: 'RipClient_Endpoint');
      return list;
    } catch (e, stack) {
      RipLogger.error('search failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<Map<String, dynamic>> trace({
    required String projectId,
    required String symbol,
    CancelToken? cancelToken,
  }) async {
    try {
      RipLogger.info('Calling trace(projectId: $projectId, symbol: "$symbol")', tag: 'RipClient_Endpoint');
      final response = await _dio.get(
        '/trace/$symbol',
        queryParameters: {'project_id': projectId},
        cancelToken: cancelToken,
      );
      final data = response.data as Map<String, dynamic>;
      final result = data['data'] as Map<String, dynamic>;
      RipLogger.success('trace succeeded: key count ${result.length}', tag: 'RipClient_Endpoint');
      return result;
    } catch (e, stack) {
      RipLogger.error('trace failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<Map<String, dynamic>> impact({
    required String projectId,
    required String symbol,
    CancelToken? cancelToken,
  }) async {
    try {
      RipLogger.info('Calling impact(projectId: $projectId, symbol: "$symbol")', tag: 'RipClient_Endpoint');
      final response = await _dio.get(
        '/impact/$symbol',
        queryParameters: {'project_id': projectId},
        cancelToken: cancelToken,
      );
      final data = response.data as Map<String, dynamic>;
      final result = data['data'] as Map<String, dynamic>;
      RipLogger.success('impact succeeded: key count ${result.length}', tag: 'RipClient_Endpoint');
      return result;
    } catch (e, stack) {
      RipLogger.error('impact failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<Map<String, dynamic>> architecture({
    required String projectId,
    CancelToken? cancelToken,
  }) async {
    try {
      RipLogger.info('Calling architecture(projectId: $projectId)', tag: 'RipClient_Endpoint');
      final response = await _dio.get(
        '/architecture',
        queryParameters: {'project_id': projectId},
        cancelToken: cancelToken,
      );
      final data = response.data as Map<String, dynamic>;
      final result = data['data'] as Map<String, dynamic>;
      RipLogger.success('architecture succeeded: key count ${result.length}', tag: 'RipClient_Endpoint');
      return result;
    } catch (e, stack) {
      RipLogger.error('architecture failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<Map<String, dynamic>> explain({
    required String projectId,
    required String topic,
    CancelToken? cancelToken,
  }) async {
    try {
      RipLogger.info('Calling explain(projectId: $projectId, topic: "$topic")', tag: 'RipClient_Endpoint');
      final response = await _dio.post('/explain', data: {
        'query': topic,
        'project_id': projectId,
      }, cancelToken: cancelToken);
      final data = response.data as Map<String, dynamic>;
      final result = data['data'] as Map<String, dynamic>? ?? {};
      RipLogger.success('explain succeeded: key count ${result.length}', tag: 'RipClient_Endpoint');
      return result;
    } catch (e, stack) {
      RipLogger.error('explain failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<Map<String, dynamic>> metrics({
    required String projectId,
    CancelToken? cancelToken,
  }) async {
    try {
      RipLogger.info('Calling metrics(projectId: $projectId)', tag: 'RipClient_Endpoint');
      final response = await _dio.get(
        '/metrics',
        queryParameters: {'project_id': projectId},
        cancelToken: cancelToken,
      );
      final data = response.data as Map<String, dynamic>;
      final result = data['data'] as Map<String, dynamic>? ?? data;
      RipLogger.success('metrics succeeded', tag: 'RipClient_Endpoint');
      return result;
    } catch (e, stack) {
      RipLogger.error('metrics failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<Map<String, dynamic>> onboard({
    required String projectId,
    CancelToken? cancelToken,
  }) async {
    try {
      RipLogger.info('Calling onboard(projectId: $projectId)', tag: 'RipClient_Endpoint');
      final response = await _dio.get(
        '/onboard',
        queryParameters: {'project_id': projectId},
        cancelToken: cancelToken,
      );
      final data = response.data as Map<String, dynamic>;
      final result = data['data'] as Map<String, dynamic>? ?? data;
      RipLogger.success('onboard succeeded', tag: 'RipClient_Endpoint');
      return result;
    } catch (e, stack) {
      RipLogger.error('onboard failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<Map<String, dynamic>> deadCode({
    required String projectId,
    CancelToken? cancelToken,
  }) async {
    try {
      RipLogger.info('Calling deadCode(projectId: $projectId)', tag: 'RipClient_Endpoint');
      final response = await _dio.get(
        '/dead-code',
        queryParameters: {'project_id': projectId},
        cancelToken: cancelToken,
      );
      final data = response.data as Map<String, dynamic>;
      final result = data['data'] as Map<String, dynamic>? ?? data;
      RipLogger.success('deadCode succeeded', tag: 'RipClient_Endpoint');
      return result;
    } catch (e, stack) {
      RipLogger.error('deadCode failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<bool> healthCheck() async {
    try {
      RipLogger.info('Calling healthCheck()', tag: 'RipClient_Endpoint');
      final response = await _dio.get('/health');
      final data = response.data as Map<String, dynamic>;
      final isHealthy = data['status'] == 'ok' ||
          data['status'] == 'ready' ||
          data['status'] == 'healthy';
      RipLogger.success('healthCheck() status: $isHealthy', tag: 'RipClient_Endpoint');
      return isHealthy;
    } catch (e) {
      RipLogger.warning('healthCheck() failed: $e', tag: 'RipClient_Endpoint');
      return false;
    }
  }
}
