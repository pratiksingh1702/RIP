import 'package:dio/dio.dart';
import '../exceptions.dart';
import '../../data/models/project.dart';
import '../../data/models/search_result.dart';
import '../../data/models/index_job.dart';
import '../../utils/logger.dart';

class RipClient {
  late final Dio _dio;
  late final String _serverUrl;

  RipClient({required String serverUrl, String? apiKey}) {
    _serverUrl = serverUrl;
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

  bool _isNotFoundError(Object error) {
    if (error is RIPNotFoundException) return true;
    if (error is DioException) {
      if (error.response?.statusCode == 404) return true;
      return error.error is RIPNotFoundException;
    }
    return false;
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
    required String folderName,
    String? subdirectory,
    String branch = 'main',
    CancelToken? cancelToken,
  }) async {
    try {
      RipLogger.info('Calling startGitIndex(gitUrl: $gitUrl, projectName: $projectName, folderName: $folderName, subdirectory: $subdirectory, branch: $branch)', tag: 'RipClient_Endpoint');
      final response = await _dio.post('/git/index', data: {
        'git_url': gitUrl,
        'project_name': projectName,
        'folder_name': folderName,
        if (subdirectory != null && subdirectory.trim().isNotEmpty)
          'subdirectory': subdirectory.trim(),
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
    String contextLevel = 'file',
    String? provider,
    String? model,
    bool diagram = false,
    bool tree = false,
    bool dependencies = false,
    bool code = false,
    bool noLlm = false,
    int maxHops = 8,
    CancelToken? cancelToken,
  }) async {
    try {
      RipLogger.info('Calling explain(projectId: $projectId, topic: "$topic")', tag: 'RipClient_Endpoint');
      final response = await _dio.post('/explain', data: {
        'query': topic,
        'project_id': projectId,
        'context_level': contextLevel,
        if (provider != null && provider.trim().isNotEmpty) 'provider': provider,
        if (model != null && model.trim().isNotEmpty) 'model': model,
        'diagram': diagram,
        'tree': tree,
        'dependencies': dependencies,
        'code': code,
        'no_llm': noLlm,
        'max_hops': maxHops,
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

  Future<Map<String, dynamic>> gatewayContext({
    required String task,
    required String sessionId,
    String? projectId,
    int maxTokens = 12000,
    String role = 'developer',
    CancelToken? cancelToken,
  }) async {
    try {
      RipLogger.info('Calling gatewayContext(sessionId: $sessionId)', tag: 'RipClient_Endpoint');
      final response = await _dio.post('/gateway/api/context', data: {
        'task': task,
        'session_id': sessionId,
        if (projectId != null) 'project_id': projectId,
        'max_tokens': maxTokens,
        'role': role,
      }, cancelToken: cancelToken);
      final data = response.data as Map<String, dynamic>;
      final result = data['data'] as Map<String, dynamic>? ?? data;
      RipLogger.success('gatewayContext succeeded', tag: 'RipClient_Endpoint');
      return result;
    } catch (e, stack) {
      RipLogger.error('gatewayContext failed', tag: 'RipClient_Endpoint', error: e, stackTrace: stack);
      rethrow;
    }
  }

  Future<Map<String, dynamic>> gatewayMetrics({CancelToken? cancelToken}) async {
    final response = await _dio.get('/gateway/api/metrics', cancelToken: cancelToken);
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> gatewaySources({String? projectId, CancelToken? cancelToken}) async {
    final response = await _dio.get(
      '/gateway/api/sources',
      queryParameters: {
        if (projectId != null) 'project_id': projectId,
      },
      cancelToken: cancelToken,
    );
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> gatewayIntegrationProjects(
    String sourceId, {
    CancelToken? cancelToken,
  }) async {
    Response<dynamic> response;
    try {
      response = await _dio.get(
        '/gateway/api/sources/$sourceId/projects',
        cancelToken: cancelToken,
      );
    } catch (error) {
      if (!_isNotFoundError(error)) rethrow;
      response = await _dio.get(
        '/gateway/api/integrations/$sourceId/projects',
        cancelToken: cancelToken,
      );
    }
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> updateGatewayIntegrationProjects(
    String sourceId,
    List<String> projectIds, {
    CancelToken? cancelToken,
  }) async {
    Response<dynamic> response;
    try {
      response = await _dio.put(
        '/gateway/api/sources/$sourceId/projects',
        data: {'project_ids': projectIds},
        cancelToken: cancelToken,
      );
    } catch (error) {
      if (!_isNotFoundError(error)) rethrow;
      response = await _dio.put(
        '/gateway/api/integrations/$sourceId/projects',
        data: {'project_ids': projectIds},
        cancelToken: cancelToken,
      );
    }
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> gatewaySourcePresets({CancelToken? cancelToken}) async {
    final response = await _dio.get('/gateway/api/sources/presets', cancelToken: cancelToken);
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> gatewayOAuthProviders({CancelToken? cancelToken}) async {
    final response = await _dio.get('/gateway/api/oauth/providers', cancelToken: cancelToken);
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> initiateGatewayOAuth(
    Map<String, dynamic> values, {
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post('/gateway/api/oauth/initiate', data: values, cancelToken: cancelToken);
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> completeGatewayOAuth(
    Map<String, dynamic> values, {
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post('/gateway/api/oauth/callback', data: values, cancelToken: cancelToken);
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> gatewayOAuthPending({CancelToken? cancelToken}) async {
    final response = await _dio.get('/gateway/api/oauth/pending', cancelToken: cancelToken);
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> gatewaySettings({CancelToken? cancelToken}) async {
    final response = await _dio.get('/gateway/settings', cancelToken: cancelToken);
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> updateGatewaySettings(
    Map<String, dynamic> values, {
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.patch('/gateway/settings', data: values, cancelToken: cancelToken);
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> createGatewaySource(
    Map<String, dynamic> values, {
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post('/gateway/api/sources', data: values, cancelToken: cancelToken);
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> updateGatewaySource(
    String sourceId,
    Map<String, dynamic> values, {
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.patch('/gateway/api/sources/$sourceId', data: values, cancelToken: cancelToken);
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<void> deleteGatewaySource(String sourceId, {CancelToken? cancelToken}) async {
    await _dio.delete('/gateway/api/sources/$sourceId', cancelToken: cancelToken);
  }

  Future<Map<String, dynamic>> replaceGatewaySourceCredential(
    String sourceId,
    String credential, {
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post(
      '/gateway/api/sources/$sourceId/credential',
      data: {'credential': credential},
      cancelToken: cancelToken,
    );
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> testGatewaySource(String sourceId, {String? projectId, CancelToken? cancelToken}) async {
    final response = await _dio.post(
      '/gateway/api/sources/$sourceId/test',
      queryParameters: {
        if (projectId != null) 'project_id': projectId,
      },
      cancelToken: cancelToken,
    );
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> reauthorizeGatewaySourceOAuth(
    String sourceId,
    Map<String, dynamic> values, {
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post(
      '/gateway/api/sources/$sourceId/oauth/reauthorize',
      data: values,
      cancelToken: cancelToken,
    );
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> revokeGatewaySourceOAuth(String sourceId, {String? projectId, CancelToken? cancelToken}) async {
    final response = await _dio.post(
      '/gateway/api/sources/$sourceId/oauth/revoke',
      queryParameters: {
        if (projectId != null) 'project_id': projectId,
      },
      cancelToken: cancelToken,
    );
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<List<dynamic>> gatewaySessions({CancelToken? cancelToken}) async {
    final response = await _dio.get('/gateway/api/sessions', cancelToken: cancelToken);
    final data = response.data;
    if (data is Map<String, dynamic>) return data['data'] as List? ?? const [];
    return data as List? ?? const [];
  }

  Future<List<dynamic>> gatewayAudit({
    String? sessionId,
    String? role,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.get(
      '/gateway/api/audit',
      queryParameters: {
        if (sessionId != null) 'session_id': sessionId,
        if (role != null) 'role': role,
      },
      cancelToken: cancelToken,
    );
    final data = response.data as Map<String, dynamic>;
    final result = data['data'] as Map<String, dynamic>? ?? data;
    return result['audit_logs'] as List? ?? const [];
  }

  Future<void> submitGatewayFeedback({
    required String sessionId,
    int? rating,
    bool? wasHelpful,
    List<String> missingContext = const [],
    List<String> irrelevantContext = const [],
    String? comment,
    String? promptId,
    CancelToken? cancelToken,
  }) async {
    await _dio.post('/gateway/api/feedback', data: {
      'session_id': sessionId,
      if (rating != null) 'rating': rating,
      if (wasHelpful != null) 'was_helpful': wasHelpful,
      'missing_context': missingContext,
      'irrelevant_context': irrelevantContext,
      if (comment != null) 'comment': comment,
      if (promptId != null) 'prompt_id': promptId,
    }, cancelToken: cancelToken);
  }

  Future<List<dynamic>> gatewayWorkflows({String? projectId, CancelToken? cancelToken}) async {
    final response = await _dio.get(
      '/gateway/api/workflows',
      queryParameters: {
        if (projectId != null) 'project_id': projectId,
      },
      cancelToken: cancelToken,
    );
    final data = response.data;
    if (data is Map<String, dynamic>) {
      return (data['data'] as List?) ?? (data['workflows'] as List?) ?? const [];
    }
    return data as List? ?? const [];
  }

  Future<Map<String, dynamic>> gatewayWorkflowPalette({CancelToken? cancelToken}) async {
    final response = await _dio.get('/gateway/api/workflows/palette/blocks', cancelToken: cancelToken);
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> gatewayPromptTemplates({CancelToken? cancelToken}) async {
    final response = await _dio.get('/gateway/api/workflows/prompt-templates', cancelToken: cancelToken);
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> createGatewayPromptTemplate({
    required String name,
    required String promptTemplate,
    List<String> variables = const [],
    String? systemPrompt,
    String visibility = 'private',
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post(
      '/gateway/api/workflows/prompt-templates',
      data: {
        'name': name,
        'prompt_template': promptTemplate,
        'variables': variables,
        if (systemPrompt != null && systemPrompt.trim().isNotEmpty) 'system_prompt': systemPrompt,
        'visibility': visibility,
      },
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createGatewayWorkflow({
    required String name,
    String scope = 'project',
    String? projectId,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post(
      '/gateway/api/workflows',
      queryParameters: {
        'name': name,
        'scope': scope,
        if (projectId != null) 'project_id': projectId,
      },
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> appendGatewayWorkflowBlock({
    required String draftId,
    required String blockId,
    required Map<String, dynamic> config,
    required Map<String, dynamic> inputBindings,
    Map<String, double>? position,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post(
      '/gateway/api/workflows/$draftId/blocks',
      data: {
        'block_id': blockId,
        'config': config,
        'input_bindings': inputBindings,
        if (position != null) 'position': position,
      },
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> patchGatewayWorkflowBlock({
    required String draftId,
    required String stepId,
    String? blockId,
    Map<String, dynamic>? config,
    Map<String, dynamic>? inputBindings,
    Map<String, double>? position,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.patch(
      '/gateway/api/workflows/$draftId/blocks/$stepId',
      data: {
        if (blockId != null) 'block_id': blockId,
        if (config != null) 'config': config,
        if (inputBindings != null) 'input_bindings': inputBindings,
        if (position != null) 'position': position,
      },
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> gatewayWorkflowCanvas({
    required String draftId,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.get('/gateway/api/workflows/$draftId/canvas', cancelToken: cancelToken);
    final data = response.data as Map<String, dynamic>;
    return data['data'] as Map<String, dynamic>? ?? data;
  }

  Future<Map<String, dynamic>> updateGatewayWorkflow({
    required String draftId,
    String? name,
    String? description,
    String? category,
    String? visibility,
    Map<String, dynamic>? canvasState,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.patch(
      '/gateway/api/workflows/$draftId',
      data: {
        if (name != null) 'name': name,
        if (description != null) 'description': description,
        if (category != null) 'category': category,
        if (visibility != null) 'visibility': visibility,
        if (canvasState != null) 'canvas_state': canvasState,
      },
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> addGatewayWorkflowWire({
    required String draftId,
    required String sourceStepId,
    required String targetStepId,
    required String targetPort,
    String sourcePort = 'output',
    Map<String, dynamic>? mapping,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post(
      '/gateway/api/workflows/$draftId/wires',
      data: {
        'source_step_id': sourceStepId,
        'source_port': sourcePort,
        'target_step_id': targetStepId,
        'target_port': targetPort,
        if (mapping != null) 'mapping': mapping,
      },
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> deleteGatewayWorkflowWire({
    required String draftId,
    required String wireId,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.delete('/gateway/api/workflows/$draftId/wires/$wireId', cancelToken: cancelToken);
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> reorderGatewayWorkflowBlocks({
    required String draftId,
    required List<String> stepOrder,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post(
      '/gateway/api/workflows/$draftId/blocks/reorder',
      data: {'step_order': stepOrder},
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> deleteGatewayWorkflowBlock({
    required String draftId,
    required String stepId,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.delete('/gateway/api/workflows/$draftId/blocks/$stepId', cancelToken: cancelToken);
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> publishGatewayWorkflow(String draftId, {CancelToken? cancelToken}) async {
    final response = await _dio.post('/gateway/api/workflows/$draftId/publish', cancelToken: cancelToken);
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> runGatewayWorkflow({
    required String draftId,
    required String query,
    String? projectId,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post(
      '/gateway/api/workflows/$draftId/run',
      data: {
        'query': query,
        if (projectId != null) 'project_id': projectId,
      },
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> gatewayWorkflowRunState({
    required String draftId,
    required String runId,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.get('/gateway/api/workflows/$draftId/runs/$runId', cancelToken: cancelToken);
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> answerGatewayWorkflowInput({
    required String draftId,
    required String runId,
    required String stepId,
    required dynamic value,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post(
      '/gateway/api/workflows/$draftId/runs/$runId/answer_missing_input',
      data: {'step_id': stepId, 'value': value},
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> approveGatewayWorkflowRun({
    required String draftId,
    required String runId,
    String? comment,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post(
      '/gateway/api/workflows/$draftId/runs/$runId/approve',
      data: {'approved': true, if (comment != null) 'comment': comment},
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> rejectGatewayWorkflowRun({
    required String draftId,
    required String runId,
    String? comment,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post(
      '/gateway/api/workflows/$draftId/runs/$runId/reject',
      data: {'approved': false, if (comment != null) 'comment': comment},
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  Uri chatPipelineWebSocketUri(String sessionId, {int afterSeq = 0}) {
    final base = Uri.parse(_serverUrl);
    final scheme = base.scheme == 'https' ? 'wss' : 'ws';
    final basePath = base.path.endsWith('/')
        ? base.path.substring(0, base.path.length - 1)
        : base.path;
    return base.replace(
      scheme: scheme,
      path: '$basePath/ws/chat/$sessionId',
      queryParameters: {'after_seq': '$afterSeq'},
    );
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

  /// Execute an AI agent for autonomous engineering tasks
  Future<Map<String, dynamic>> executeAgent({
    required String query,
    String? modelPreference,
    String? projectId,
    int maxTurns = 50,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post('/gateway/api/agent/execute', data: {
      'query': query,
      if (modelPreference != null) 'model_preference': modelPreference,
      if (projectId != null) 'project_id': projectId,
      'max_turns': maxTurns,
    }, cancelToken: cancelToken);
    return response.data as Map<String, dynamic>;
  }

  /// Get the current state of an agent run
  Future<Map<String, dynamic>> getAgentRun(String runId, {CancelToken? cancelToken}) async {
    final response = await _dio.get('/gateway/api/agent/runs/$runId', cancelToken: cancelToken);
    return response.data as Map<String, dynamic>;
  }

  /// List all agent runs
  Future<Map<String, dynamic>> listAgentRuns({CancelToken? cancelToken}) async {
    final response = await _dio.get('/gateway/api/agent/runs', cancelToken: cancelToken);
    return response.data as Map<String, dynamic>;
  }

  /// List available agent tools
  Future<Map<String, dynamic>> listAgentTools({CancelToken? cancelToken}) async {
    final response = await _dio.get('/gateway/api/agent/tools', cancelToken: cancelToken);
    return response.data as Map<String, dynamic>;
  }


  /// List available LLM configurations
  Future<Map<String, dynamic>> listLLMConfigs({CancelToken? cancelToken}) async {
    final response = await _dio.get('/gateway/api/workflows/llm-configs', cancelToken: cancelToken);
    return response.data as Map<String, dynamic>;
  }

  /// Add a custom LLM configuration
  Future<Map<String, dynamic>> addLLMConfig({
    required String configId,
    required String provider,
    required String model,
    String? apiKey,
    String? baseUrl,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post('/gateway/api/workflows/llm-configs', data: {
      'config_id': configId,
      'provider': provider,
      'model': model,
      if (apiKey != null && apiKey.isNotEmpty) 'api_key': apiKey,
      if (baseUrl != null && baseUrl.isNotEmpty) 'base_url': baseUrl,
    }, cancelToken: cancelToken);
    return response.data as Map<String, dynamic>;
  }

  /// Update an LLM configuration
  Future<Map<String, dynamic>> updateLLMConfig({
    required String configId,
    String? provider,
    String? model,
    String? apiKey,
    String? baseUrl,
    CancelToken? cancelToken,
  }) async {
    final data = <String, dynamic>{};
    if (provider != null) data['provider'] = provider;
    if (model != null) data['model'] = model;
    if (apiKey != null) data['api_key'] = apiKey.isEmpty ? null : apiKey;
    if (baseUrl != null) data['base_url'] = baseUrl.isEmpty ? null : baseUrl;
    final response = await _dio.patch(
      '/gateway/api/workflows/llm-configs/$configId',
      data: data,
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  /// Remove an LLM configuration
  Future<void> deleteLLMConfig(String configId, {CancelToken? cancelToken}) async {
    await _dio.delete('/gateway/api/workflows/llm-configs/$configId', cancelToken: cancelToken);
  }

  /// Update an LLM configuration



  /// Sync active project to server
  Future<void> setActiveProject(String projectId) async {
    try {
      await _dio.post('/gateway/api/projects/active', data: {'project_id': projectId});
    } catch (_) {}
  }

  /// Clear active project on server
  Future<void> clearActiveProject() async {
    try {
      await _dio.post('/gateway/api/projects/active', data: {'project_id': null});
    } catch (_) {}
  }

  /// List prompt templates (used by workflow builder)
  Future<Map<String, dynamic>> listGatewayPromptTemplates({CancelToken? cancelToken}) async {
    final response = await _dio.get('/gateway/api/workflows/prompt-templates', cancelToken: cancelToken);
    return response.data as Map<String, dynamic>;
  }

}



