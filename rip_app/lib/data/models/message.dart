import 'package:equatable/equatable.dart';
import '../../domain/enums/message_type.dart';

class Message extends Equatable {
  final String id;
  final String content;
  final bool isUser;
  final MessageType type;
  final DateTime timestamp;
  final Map<String, dynamic>? metadata;

  const Message({
    required this.id,
    required this.content,
    required this.isUser,
    this.type = MessageType.text,
    required this.timestamp,
    this.metadata,
  });

  Message copyWith({
    String? id,
    String? content,
    bool? isUser,
    MessageType? type,
    DateTime? timestamp,
    Map<String, dynamic>? metadata,
  }) {
    return Message(
      id: id ?? this.id,
      content: content ?? this.content,
      isUser: isUser ?? this.isUser,
      type: type ?? this.type,
      timestamp: timestamp ?? this.timestamp,
      metadata: metadata ?? this.metadata,
    );
  }

  @override
  List<Object?> get props => [
        id,
        content,
        isUser,
        type,
        timestamp,
        metadata,
      ];
}
