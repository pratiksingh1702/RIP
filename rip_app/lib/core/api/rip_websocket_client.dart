import 'dart:async';
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
      final uri = Uri.parse(
        '${serverUrl.replaceFirst('http://', 'ws://').replaceFirst('https://', 'wss://')}/ws/index/$jobId',
      );
      RipLogger.info('WebSocket URI: $uri', tag: 'RipWebSocketClient');

      _channel = WebSocketChannel.connect(uri);
      RipLogger.success('Connected', tag: 'RipWebSocketClient');
      
      _channel!.stream.listen(
        (data) {
          RipLogger.info('Received data: $data', tag: 'RipWebSocketClient');
          try {
            final decoded = data is String
                ? data
                : String.fromCharCodes(data as List<int>);
            _controller.add({'data': decoded});
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
