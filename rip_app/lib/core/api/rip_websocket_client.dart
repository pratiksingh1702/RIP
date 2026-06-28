import 'dart:async';
import 'dart:developer';
import 'package:web_socket_channel/web_socket_channel.dart';

class RipWebSocketClient {
  final String serverUrl;
  final String? apiKey;
  WebSocketChannel? _channel;
  final StreamController<Map<String, dynamic>> _controller = StreamController.broadcast();

  RipWebSocketClient({required this.serverUrl, this.apiKey}) {
    log('[RipWebSocketClient] Created with serverUrl: $serverUrl', name: 'RipWebSocketClient');
  }

  Stream<Map<String, dynamic>> get stream => _controller.stream;

  Future<void> connect(String jobId) async {
    log('[RipWebSocketClient] Connecting for jobId: $jobId', name: 'RipWebSocketClient');
    try {
      final uri = Uri.parse(
        '${serverUrl.replaceFirst('http://', 'ws://').replaceFirst('https://', 'wss://')}/ws/index/$jobId',
      );
      log('[RipWebSocketClient] WebSocket URI: $uri', name: 'RipWebSocketClient');

      // Note: web_socket_channel v2 doesn't support headers parameter
      // For headers support, you'd need a different implementation
      _channel = WebSocketChannel.connect(uri);
      log('[RipWebSocketClient] Connected', name: 'RipWebSocketClient');
      _channel!.stream.listen(
        (data) {
          log('[RipWebSocketClient] Received data: $data', name: 'RipWebSocketClient');
          try {
            final decoded = data is String
                ? data
                : String.fromCharCodes(data as List<int>);
            // For simplicity, we'll handle both raw strings and JSON
            // In a real app, you'd parse JSON properly
            if (decoded.startsWith('{')) {
              // TODO: Parse JSON properly
            }
            _controller.add({'data': decoded});
          } catch (e) {
            log('[RipWebSocketClient] Error decoding data: $e', name: 'RipWebSocketClient', error: e);
            _controller.add({'error': e.toString()});
          }
        },
        onError: (error) {
          log('[RipWebSocketClient] Stream error: $error', name: 'RipWebSocketClient', error: error);
          _controller.add({'error': error.toString()});
        },
        onDone: () {
          log('[RipWebSocketClient] Stream done', name: 'RipWebSocketClient');
          _controller.add({'done': true});
        },
      );
    } catch (e) {
      log('[RipWebSocketClient] Error connecting: $e', name: 'RipWebSocketClient', error: e);
      _controller.add({'error': e.toString()});
    }
  }

  void disconnect() {
    log('[RipWebSocketClient] Disconnecting', name: 'RipWebSocketClient');
    _channel?.sink.close();
    _channel = null;
  }

  void dispose() {
    log('[RipWebSocketClient] Disposing', name: 'RipWebSocketClient');
    disconnect();
    _controller.close();
  }
}
