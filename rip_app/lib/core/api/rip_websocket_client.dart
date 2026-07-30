import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../utils/logger.dart';

class RipWebSocketClient {
  final String serverUrl;
  final String? apiKey;
  WebSocketChannel? _channel;
  final StreamController<Map<String, dynamic>> _controller = StreamController.broadcast();

  RipWebSocketClient({required this.serverUrl, this.apiKey}) {
    RipLogger.info('Created with serverUrl: $serverUrl', tag: 'RipWebSocketClient');
  }

  Stream<Map<String, dynamic>> get stream => _controller.stream;

  Future<void> connect(String jobId) async {
    RipLogger.info('Connecting for jobId: $jobId', tag: 'RipWebSocketClient');
    try {
      final uri = _buildIndexUri(jobId);
      RipLogger.info('WebSocket URI: $uri', tag: 'RipWebSocketClient');

      _channel = IOWebSocketChannel.connect(
        uri,
        headers: apiKey != null && apiKey!.isNotEmpty
            ? {'Authorization': 'Bearer $apiKey'}
            : null,
      );
      RipLogger.success('Connected', tag: 'RipWebSocketClient');
      
      _channel!.stream.listen(
        (data) {
          RipLogger.info('Received data: $data', tag: 'RipWebSocketClient');
          try {
            final decoded = data is String
                ? data
                : String.fromCharCodes(data as List<int>);
            final json = jsonDecode(decoded);
            if (json is Map<String, dynamic>) {
              _controller.add(json);
            } else {
              _controller.add({'data': decoded});
            }
          } catch (e) {
            RipLogger.error('Error decoding data: $e', tag: 'RipWebSocketClient', error: e);
            _controller.add({'error': e.toString()});
          }
        },
        onError: (error) {
          RipLogger.error('Stream error: $error', tag: 'RipWebSocketClient', error: error);
          _controller.add({'error': error.toString()});
        },
        onDone: () {
          RipLogger.warning('Stream done', tag: 'RipWebSocketClient');
          _controller.add({'done': true});
        },
      );
    } catch (e) {
      RipLogger.error('Error connecting: $e', tag: 'RipWebSocketClient', error: e);
      _controller.add({'error': e.toString()});
    }
  }

  Uri _buildIndexUri(String jobId) {
    final base = Uri.parse(serverUrl.trim());
    final scheme = base.scheme == 'https' ? 'wss' : 'ws';
    return base.replace(
      scheme: scheme,
      path: '/ws/index/$jobId',
      query: null,
      fragment: null,
    );
  }

  Future<void> connectJobs() async {
    RipLogger.info('Connecting for global jobs stream', tag: 'RipWebSocketClient');
    try {
      final uri = _buildJobsUri();
      RipLogger.info('WebSocket URI: $uri', tag: 'RipWebSocketClient');

      _channel = IOWebSocketChannel.connect(
        uri,
        headers: apiKey != null && apiKey!.isNotEmpty
            ? {'Authorization': 'Bearer $apiKey'}
            : null,
      );
      RipLogger.success('Connected jobs WS stream', tag: 'RipWebSocketClient');

      _channel!.stream.listen(
        (data) {
          try {
            final decoded = data is String
                ? data
                : String.fromCharCodes(data as List<int>);
            final json = jsonDecode(decoded);
            if (json is List) {
              _controller.add({'jobs': json});
            } else if (json is Map<String, dynamic>) {
              _controller.add(json);
            }
          } catch (e) {
            RipLogger.error('Error decoding jobs stream: $e', tag: 'RipWebSocketClient', error: e);
          }
        },
        onError: (error) {
          RipLogger.error('Jobs stream error: $error', tag: 'RipWebSocketClient', error: error);
        },
        onDone: () {
          RipLogger.warning('Jobs stream done', tag: 'RipWebSocketClient');
        },
      );
    } catch (e) {
      RipLogger.error('Error connecting jobs WS: $e', tag: 'RipWebSocketClient', error: e);
    }
  }

  Uri _buildJobsUri() {
    final base = Uri.parse(serverUrl.trim());
    final scheme = base.scheme == 'https' ? 'wss' : 'ws';
    return base.replace(
      scheme: scheme,
      path: '/ws/jobs',
      query: null,
      fragment: null,
    );
  }

  void disconnect() {
    RipLogger.info('Disconnecting', tag: 'RipWebSocketClient');
    _channel?.sink.close();
    _channel = null;
  }

  void dispose() {
    RipLogger.info('Disposing', tag: 'RipWebSocketClient');
    disconnect();
    _controller.close();
  }
}
