data "aws_caller_identity" "atual" {}

resource "aws_s3_bucket" "evidencias" {
  bucket = "${var.prefixo}-${data.aws_caller_identity.atual.account_id}"

  # Guarda dado pessoal (LGPD): não pode ser destruído sem querer
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "evidencias" {
  bucket = aws_s3_bucket.evidencias.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidencias" {
  bucket = aws_s3_bucket.evidencias.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "evidencias" {
  bucket = aws_s3_bucket.evidencias.id

  rule {
    id     = "expirar-evidencias"
    status = "Enabled"

    filter {}

    expiration {
      days = var.dias_para_expirar
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

data "aws_iam_policy_document" "somente_https" {
  statement {
    sid     = "NegarHttpSemTls"
    effect  = "Deny"
    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.evidencias.arn,
      "${aws_s3_bucket.evidencias.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "evidencias" {
  bucket = aws_s3_bucket.evidencias.id
  policy = data.aws_iam_policy_document.somente_https.json

  depends_on = [aws_s3_bucket_public_access_block.evidencias]
}