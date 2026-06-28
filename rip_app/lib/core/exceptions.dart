class RIPAuthException implements Exception {
  final String message;
  RIPAuthException(this.message);
}

class RIPNotFoundException implements Exception {
  final String message;
  RIPNotFoundException(this.message);
}

class RIPConnectionException implements Exception {
  final String message;
  RIPConnectionException(this.message);
}

class RIPServerException implements Exception {
  final String message;
  RIPServerException(this.message);
}
