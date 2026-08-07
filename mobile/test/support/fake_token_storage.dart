import 'package:cloudestorage/features/auth/data/token_storage.dart';

class FakeTokenStorage implements TokenStorage {
  FakeTokenStorage({this.token});

  String? token;
  Object? readError;
  Object? writeError;
  Object? deleteError;

  @override
  Future<String?> read() async {
    if (readError != null) throw readError!;
    return token;
  }

  @override
  Future<void> write(String value) async {
    if (writeError != null) throw writeError!;
    token = value;
  }

  @override
  Future<void> delete() async {
    if (deleteError != null) throw deleteError!;
    token = null;
  }
}
