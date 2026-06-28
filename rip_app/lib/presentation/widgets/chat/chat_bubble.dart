import 'package:flutter/material.dart';
import '../../../data/models/message.dart';
import 'user_message.dart';
import 'rip_message.dart';

class ChatBubble extends StatelessWidget {
  final Message message;

  const ChatBubble({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    if (message.isUser) {
      return UserMessage(message: message);
    } else {
      return RipMessage(message: message);
    }
  }
}
