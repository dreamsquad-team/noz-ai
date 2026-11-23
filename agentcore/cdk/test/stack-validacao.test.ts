import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { AgentCoreStack } from '../lib/cdk-stack';

function criarTemplate() {
  const app = new cdk.App();
  const stack = new AgentCoreStack(app, 'TestStack', {
    spec: {
      name: 'testproject',
      version: 1,
      managedBy: 'CDK' as const,
      runtimes: [],
      memories: [],
      credentials: [],
      evaluators: [],
      onlineEvalConfigs: [],
      configBundles: [],
      policyEngines: [],
      payments: [],
      agentCoreGateways: [],
      mcpRuntimeTools: [],
      unassignedTargets: [],
      datasets: [],
      knowledgeBases: [],
    },
  });
  return Template.fromStack(stack);
}

test('a stack inclui as quatro filas e o bucket de evidências', () => {
  const template = criarTemplate();
  template.resourceCountIs('AWS::SQS::Queue', 4);
  template.resourceCountIs('AWS::S3::Bucket', 1);
});

test.each(['FilaEntradaUrl', 'FilaSaidaUrl', 'BucketEvidenciasNome'])('a stack expõe a saída %s', nome => {
  expect(Object.keys(criarTemplate().findOutputs(nome))).toContain(nome);
});
