import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { BucketEvidencias } from '../lib/bucket-evidencias';

function criarTemplate() {
  const app = new cdk.App();
  const stack = new cdk.Stack(app, 'TestStack');
  new BucketEvidencias(stack, 'Evidencias');
  return Template.fromStack(stack);
}

test('cria um único bucket', () => {
  criarTemplate().resourceCountIs('AWS::S3::Bucket', 1);
});

test('o bucket bloqueia todo acesso público', () => {
  criarTemplate().hasResourceProperties('AWS::S3::Bucket', {
    PublicAccessBlockConfiguration: {
      BlockPublicAcls: true,
      BlockPublicPolicy: true,
      IgnorePublicAcls: true,
      RestrictPublicBuckets: true,
    },
  });
});

test('o bucket é criptografado com SSE-S3', () => {
  criarTemplate().hasResourceProperties('AWS::S3::Bucket', {
    BucketEncryption: {
      ServerSideEncryptionConfiguration: [{ ServerSideEncryptionByDefault: { SSEAlgorithm: 'AES256' } }],
    },
  });
});

test('o bucket expira os objetos em 90 dias', () => {
  criarTemplate().hasResourceProperties('AWS::S3::Bucket', {
    LifecycleConfiguration: {
      Rules: [
        {
          ExpirationInDays: 90,
          AbortIncompleteMultipartUpload: { DaysAfterInitiation: 7 },
          Status: 'Enabled',
        },
      ],
    },
  });
});

test('o bucket recusa acesso sem HTTPS', () => {
  criarTemplate().hasResourceProperties('AWS::S3::BucketPolicy', {
    PolicyDocument: {
      Statement: [
        {
          Action: 's3:*',
          Effect: 'Deny',
          Condition: { Bool: { 'aws:SecureTransport': 'false' } },
        },
      ],
    },
  });
});

test('o bucket é retido se a stack for destruída', () => {
  criarTemplate().hasResource('AWS::S3::Bucket', {
    DeletionPolicy: 'Retain',
    UpdateReplacePolicy: 'Retain',
  });
});
