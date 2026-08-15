/// First-run wizard widget (APP-06).
///
/// Two-step wizard: LLM provider + API key → model confirmation.
/// After completion, the app starts directly to the chat UI.
library;

import 'package:flutter/material.dart';

import 'package:flutter_app/wizard/llm_provider.dart';
import 'package:flutter_app/wizard/wizard_models.dart';

/// The first-run wizard widget.
class FirstRunWizard extends StatefulWidget {
  /// Creates the first-run wizard.
  const FirstRunWizard({
    super.key,
    required this.onComplete,
  });

  /// Called when the wizard is completed.
  /// Receives the final [WizardState].
  final void Function(WizardState state) onComplete;

  @override
  State<FirstRunWizard> createState() => _FirstRunWizardState();
}

class _FirstRunWizardState extends State<FirstRunWizard> {
  WizardState _state = const WizardState();
  final _apiKeyController = TextEditingController();
  final _modelController = TextEditingController();
  final _baseUrlController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _modelController.text = _state.selectedProvider.defaultModel;
    _baseUrlController.text = _state.selectedProvider.defaultBaseUrl ?? '';
  }

  @override
  void dispose() {
    _apiKeyController.dispose();
    _modelController.dispose();
    _baseUrlController.dispose();
    super.dispose();
  }

  void _nextStep() {
    if (!_state.canProceed) return;

    if (_state.step == WizardStep.modelConfirmation) {
      widget.onComplete(_state.copyWith(step: WizardStep.complete));
      return;
    }

    final nextStep = WizardStep.values[_state.step.index + 1];
    setState(() {
      _state = _state.copyWith(step: nextStep);
    });
  }

  void _previousStep() {
    if (_state.step == WizardStep.providerAndKey) return;
    final prevStep = WizardStep.values[_state.step.index - 1];
    setState(() {
      _state = _state.copyWith(step: prevStep);
    });
  }

  void _selectProvider(LlmProvider provider) {
    setState(() {
      _state = _state.copyWith(
        selectedProvider: provider,
        modelConfig: provider.defaultModel,
      );
      _modelController.text = provider.defaultModel;
      _baseUrlController.text = provider.defaultBaseUrl ?? '';
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          child: Container(
            constraints: const BoxConstraints(maxWidth: 600),
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildHeader(),
                const SizedBox(height: 32),
                _buildStepContent(),
                const SizedBox(height: 24),
                _buildNavigation(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      children: [
        const Text(
          '欢迎使用墨律',
          style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        Text(
          '步骤 ${_state.step.index + 1} / 2',
          style: TextStyle(color: Colors.grey[600]),
        ),
        const SizedBox(height: 16),
        LinearProgressIndicator(
          value: (_state.step.index + 1) / 2,
        ),
      ],
    );
  }

  Widget _buildStepContent() {
    return switch (_state.step) {
      WizardStep.providerAndKey => _buildProviderAndKeyStep(),
      WizardStep.modelConfirmation => _buildModelConfirmationStep(),
      WizardStep.complete => const Center(child: Text('完成')),
    };
  }

  Widget _buildProviderAndKeyStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('选择 LLM 供应商并输入 API 密钥',
            style: TextStyle(fontSize: 18)),
        const SizedBox(height: 8),
        const Text(
          '密钥将安全存储在系统凭据库中，不会出现在配置文件或日志中。',
          style: TextStyle(color: Colors.grey),
        ),
        const SizedBox(height: 24),
        // Provider dropdown
        DropdownButtonFormField<LlmProvider>(
          initialValue: _state.selectedProvider,
          decoration: const InputDecoration(
            labelText: '供应商',
            border: OutlineInputBorder(),
            prefixIcon: Icon(Icons.cloud),
          ),
          items: LlmProvider.all.map((provider) {
            return DropdownMenuItem(
              value: provider,
              child: Text(provider.displayName),
            );
          }).toList(),
          onChanged: (provider) {
            if (provider != null) _selectProvider(provider);
          },
        ),
        const SizedBox(height: 16),
        // API key field
        TextField(
          controller: _apiKeyController,
          obscureText: true,
          decoration: InputDecoration(
            labelText: 'API 密钥',
            hintText: _state.selectedProvider.keyHint,
            border: const OutlineInputBorder(),
            prefixIcon: const Icon(Icons.key),
          ),
          onChanged: (value) {
            setState(() {
              _state = _state.copyWith(apiKey: value);
            });
          },
        ),
        const SizedBox(height: 16),
        // Optional base URL field
        if (_state.selectedProvider.baseUrlEnvVar != null) ...[
          TextField(
            controller: _baseUrlController,
            decoration: const InputDecoration(
              labelText: 'Base URL（可选，留空使用默认值）',
              hintText: 'https://api.example.com',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.link),
            ),
            onChanged: (value) {
              setState(() {
                _state = _state.copyWith(
                    baseUrl: value.isEmpty ? null : value);
              });
            },
          ),
          const SizedBox(height: 16),
        ],
        // Provider-specific help text
        _buildProviderHelp(),
      ],
    );
  }

  Widget _buildProviderHelp() {
    final provider = _state.selectedProvider;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${provider.displayName} 配置说明',
                style: const TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text(
              '环境变量: ${provider.apiKeyEnvVar}',
              style: const TextStyle(fontSize: 12, color: Colors.grey),
            ),
            if (provider.defaultBaseUrl != null)
              Text(
                '默认 Base URL: ${provider.defaultBaseUrl}',
                style: const TextStyle(fontSize: 12, color: Colors.grey),
              ),
            const SizedBox(height: 8),
            Text(
              _getProviderHelpText(provider),
              style: const TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  String _getProviderHelpText(LlmProvider provider) {
    switch (provider.id) {
      case 'deepseek':
        return '访问 platform.deepseek.com 创建 API 密钥';
      case 'openai':
        return '访问 platform.openai.com 创建 API 密钥';
      case 'anthropic':
        return '访问 console.anthropic.com 创建 API 密钥';
      case 'custom':
        return '输入自定义供应商的 API 密钥和 Base URL';
      default:
        return '';
    }
  }

  Widget _buildModelConfirmationStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('确认模型配置', style: TextStyle(fontSize: 18)),
        const SizedBox(height: 24),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Text('供应商',
                        style: TextStyle(fontWeight: FontWeight.bold)),
                    const Spacer(),
                    Text(_state.selectedProvider.displayName),
                  ],
                ),
                const SizedBox(height: 12),
                const Text('模型',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                TextField(
                  controller: _modelController,
                  decoration: const InputDecoration(
                    labelText: '模型名称',
                    border: OutlineInputBorder(),
                  ),
                  onChanged: (value) {
                    setState(() {
                      _state = _state.copyWith(modelConfig: value);
                    });
                  },
                ),
                const SizedBox(height: 12),
                if (_state.baseUrl != null && _state.baseUrl!.isNotEmpty) ...[
                  Row(
                    children: [
                      const Text('Base URL',
                          style: TextStyle(fontWeight: FontWeight.bold)),
                      const Spacer(),
                      Expanded(
                        child: Text(
                          _state.baseUrl!,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                ],
                const Text(
                  '如需更改模型名称，请直接编辑上方输入框。',
                  style: TextStyle(color: Colors.grey, fontSize: 12),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildNavigation() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        if (_state.step != WizardStep.providerAndKey)
          TextButton(
            onPressed: _previousStep,
            child: const Text('上一步'),
          )
        else
          const SizedBox(),
        ElevatedButton(
          onPressed: _state.canProceed ? _nextStep : null,
          child: Text(
            _state.step == WizardStep.modelConfirmation ? '完成' : '下一步',
          ),
        ),
      ],
    );
  }
}
