import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/api/rip_client.dart';
import '../../../core/design/app_colors.dart';
import '../../providers/connection_provider.dart';

class JITAuthWidget extends ConsumerStatefulWidget {
  final Map<String, dynamic> challenge;
  final VoidCallback onAuthenticated;

  const JITAuthWidget({
    super.key,
    required this.challenge,
    required this.onAuthenticated,
  });

  @override
  ConsumerState<JITAuthWidget> createState() => _JITAuthWidgetState();
}

class _JITAuthWidgetState extends ConsumerState<JITAuthWidget> {
  final TextEditingController _credentialController = TextEditingController();
  bool _submitting = false;
  String? _error;

  String get sourceId => '${widget.challenge['source_id']}';
  String get sourceName => '${widget.challenge['source_name'] ?? sourceId}';
  String get authType => '${widget.challenge['auth_type']}';
  String get instructions => '${widget.challenge['instructions'] ?? 'Authentication required'}';

  Future<void> _submitToken() async {
    final cred = _credentialController.text.trim();
    if (cred.isEmpty) return;

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      final client = ref.read(ripClientProvider);
      await client.replaceGatewaySourceCredential(sourceId, cred);
      if (mounted) {
        widget.onAuthenticated();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Auth failed: $e';
          _submitting = false;
        });
      }
    }
  }

  Future<void> _startOAuth() async {
    final authUrl = widget.challenge['authorization_url'];
    if (authUrl != null && authUrl.toString().isNotEmpty) {
      final uri = Uri.tryParse(authUrl.toString());
      if (uri != null && await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      }
      return;
    }

    // Trigger reauthorize from backend
    try {
      final client = ref.read(ripClientProvider);
      final res = await client.reauthorizeGatewaySourceOAuth(sourceId, {
        'redirect_uri': 'riplink://oauth/callback',
        'client_type': 'mobile',
      });
      final url = res['authorization_url'] ?? res['url'];
      if (url != null) {
        final uri = Uri.parse(url.toString());
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _error = 'Could not start OAuth: $e');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.primary.withOpacity(0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.primary.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.lock_clock_outlined, color: AppColors.primary, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Authentication Required: $sourceName',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(instructions, style: TextStyle(fontSize: 12, color: AppColors.textSecondary)),
          const SizedBox(height: 10),

          if (authType == 'oauth2')
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _startOAuth,
                icon: const Icon(Icons.open_in_browser_rounded, size: 18),
                label: Text('Authenticate $sourceName via 1-Tap OAuth'),
              ),
            )
          else ...[
            TextField(
              controller: _credentialController,
              obscureText: true,
              decoration: InputDecoration(
                hintText: 'Enter API Key / Token for $sourceName',
                isDense: true,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
              ),
            ),
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _submitting ? null : _submitToken,
                child: _submitting
                    ? const SizedBox.square(dimension: 16, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Submit Credential & Auto-Resume'),
              ),
            ),
          ],

          if (_error != null) ...[
            const SizedBox(height: 6),
            Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 11)),
          ],
        ],
      ),
    );
  }
}
