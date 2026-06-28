import 'dart:developer';
import 'package:dio/dio.dart';
import '../exceptions.dart';
import '../../data/models/project.dart';
import '../../data/models/search_result.dart';
import '../../data/models/index_job.dart';

class RipClient {
  late final Dio _dio;

  RipClient({required String serverUrl, String? apiKey}) {
    log('[RipClient] Initializing with serverUrl: $serverUrl, apiKey: ${apiKey != null ? "***" : "null"}', name: 'RipClient');
    _dio = Dio(BaseOptions(
      baseUrl: serverUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
    ));

    if (apiKey != null && apiKey.isNotEmpty) {
      _dio.options.headers['Authorization'] = 'Bearer $apiKey';
      log('[RipClient] Added Authorization header', name: 'RipClient');
    }

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        log('[RipClient] Request: ${options.method} ${options.uri}', name: 'RipClient');
        log('[RipClient] Request headers: ${options.headers}', name: 'RipClient');
        log('[RipClient] Request data: ${options.data}', name: 'RipClient');
        handler.next(options);
      },
      onResponse: (response, handler) {
        log('[RipClient] Response: ${response.statusCode} ${response.realUri}', name: 'RipClient');
        log('[RipClient] Response data: ${response.data}', name: 'RipClient');
        handler.next(response);
      },
      onError: (error, handler) {
        log('[RipClient] Error: ${error.type} ${error.message}', name: 'RipClient', error: error);
        log('[RipClient] Error response: ${error.response}', name: 'RipClient', error: error);
        if (error.response?.statusCode == 401) {
          throw RIPAuthException('Invalid or missing API key');
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

  Future<List<Project>> listProjects() async {
    final response = await _dio.get('/projects/');
    final List<dynamic> data = response.data as List;
    return data.map((j) => Project.fromJson(j as Map<String, dynamic>)).toList();
  }

  Future<Project> getProject(String projectId) async {
    final response = await _dio.get('/projects/$projectId');
    return Project.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteProject(String projectId) async {
    await _dio.delete('/projects/$projectId');
  }

  Future<IndexJob> startGitIndex({
    required String gitUrl,
    required String projectName,
    String branch = 'main',
  }) async {
    final response = await _dio.post('/git/index', data: {
      'git_url': gitUrl,
      'project_name': projectName,
      'branch': branch,
    });
    return IndexJob.fromJson(response.data as Map<String, dynamic>);
  }

  Future<IndexJob> getJobStatus(String jobId) async {
    final response = await _dio.get('/git/status/$jobId');
    return IndexJob.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<SearchResult>> search({
    required String projectId,
    required String query,
    int limit = 10,
  }) async {
    final response = await _dio.get('/search', queryParameters: {
      'q': query,
      'project_id': projectId,
      'top': limit,
    });

    final data = response.data as Map<String, dynamic>;
    final List<dynamic> results = data['data'] as List? ?? [];
    return results
        .map((r) => SearchResult.fromJson(r as Map<String, dynamic>))
        .toList();
  }

  Future<Map<String, dynamic>> trace({
    required String projectId,
    required String symbol,
  }) async {
    final response = await _dio.get(
      '/trace/$symbol',
      queryParameters: {'project_id': projectId},
    );
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> impact({
    required String projectId,
    required String symbol,
  }) async {
    final response = await _dio.get(
      '/impact/$symbol',
      queryParameters: {'project_id': projectId},
    );
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> architecture({required String projectId}) async {
    final response = await _dio.get(
      '/architecture',
      queryParameters: {'project_id': projectId},
    );
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> explain({
    required String projectId,
    required String topic,
  }) async {
    final response = await _dio.post('/explain', data: {
      'symbol': topic,
      'project_id': projectId,
    });
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? {};
  }

  Future<bool> healthCheck() async {
    try {
      final response = await _dio.get('/health');
      final data = response.data as Map<String, dynamic>;
      return data['status'] == 'ok' ||
          data['status'] == 'ready' ||
          data['status'] == 'healthy';
    } catch (e) {
      return false;
    }
  }
}
