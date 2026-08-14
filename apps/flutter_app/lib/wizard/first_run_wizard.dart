/// First-run wizard widget (APP-06).
///
/// Three-step wizard: practice area → API key → model confirmation.
/// After completion, the app starts directly to the chat UI.
library;

import 'package:flutter/material.dart';

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
    if (_state.step == WizardStep.practiceArea) return;
    final prevStep = WizardStep.values[_state.step.index - 1];
    setState(() {
      _state = _state.copyWith(step: prevStep);
    });
  }

  void _selectPracticeArea(PracticeAreaOption option) {
    setState(() {
      _state = _state.copyWith(selectedPracticeArea: option);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Container(
          constraints: const BoxConstraints(maxWidth: 600),
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildHeader(),
              const SizedBox(height: 32),
              Expanded(child: _buildStepContent()),
              const SizedBox(height: 24),
              _buildNavigation(),
            ],
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
          '步骤 ${_state.step.index + 1} / 3',
          style: TextStyle(color: Colors.grey[600]),
        ),
        const SizedBox(height: 16),
        LinearProgressIndicator(
          value: (_state.step.index + 1) / 3,
        ),
      ],
    );
  }

  Widget _buildStepContent() {
    return switch (_state.step) {
      WizardStep.practiceArea => _buildPracticeAreaStep(),
      WizardStep.apiKey => _buildApiKeyStep(),
      WizardStep.modelConfirmation => _buildModelConfirmationStep(),
      WizardStep.complete => const Center(child: Text('完成')),
    };
  }

  Widget _buildPracticeAreaStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('选择您的执业方向', style: TextStyle(fontSize: 18)),
        const SizedBox(height: 16),
        Expanded(
          child: ListView(
            children: PracticeAreas.all.map((option) {
              final isSelected = _state.selectedPracticeArea?.presetName ==
                  option.presetName;
              return Card(
                color: isSelected
                    ? Theme.of(context).colorScheme.primaryContainer
                    : null,
                child: ListTile(
                  leading: Icon(option.icon),
                  title: Text(option.name),
                  subtitle: Text(option.description),
                  trailing: isSelected
                      ? const Icon(Icons.check_circle)
                      : null,
                  onTap: () => _selectPracticeArea(option),
                ),
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildApiKeyStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('输入 DeepSeek API 密钥', style: TextStyle(fontSize: 18)),
        const SizedBox(height: 8),
        const Text(
          '密钥将安全存储在系统凭据库中，不会出现在配置文件或日志中。',
          style: TextStyle(color: Colors.grey),
        ),
        const SizedBox(height: 24),
        TextField(
          obscureText: true,
          decoration: const InputDecoration(
            labelText: 'API 密钥',
            hintText: 'sk-...',
            border: OutlineInputBorder(),
            prefixIcon: Icon(Icons.key),
          ),
          onChanged: (value) {
            setState(() {
              _state = _state.copyWith(apiKey: value);
            });
          },
        ),
        const SizedBox(height: 16),
        const Text(
          '获取密钥：访问 platform.deepseek.com 创建 API 密钥',
          style: TextStyle(color: Colors.grey, fontSize: 12),
        ),
      ],
    );
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
                const Text('默认模型', style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                Text('供应商: DeepSeek'),
                Text('模型: ${_state.modelConfig}'),
                const SizedBox(height: 8),
                const Text(
                  '默认使用 DeepSeek 官方路由。如需更改，请在业主模式下配置。',
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
        if (_state.step != WizardStep.practiceArea)
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
