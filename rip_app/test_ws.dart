import 'package:web_socket_channel/io.dart';

void main() {
  try {
    IOWebSocketChannel.connect(Uri.parse('ws://localhost'), pingInterval: Duration(seconds: 10));
    print('pingInterval supported');
  } catch (e) {
    print(e);
  }
}
