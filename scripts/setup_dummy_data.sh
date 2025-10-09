#!/bin/bash

# 모구 AI 추천 시스템 더미 데이터 생성 및 삽입 스크립트

echo "🚀 모구 AI 추천 시스템 더미 데이터 생성 시작..."

# 1. 더미 데이터 생성
echo "📊 1단계: 더미 데이터 생성 중..."
python scripts/generate_dummy_data.py

if [ $? -eq 0 ]; then
    echo "✅ 더미 데이터 생성 완료"
else
    echo "❌ 더미 데이터 생성 실패"
    exit 1
fi

# 2. 데이터베이스에 삽입
echo "💾 2단계: 데이터베이스 삽입 중..."
python scripts/insert_dummy_data.py

if [ $? -eq 0 ]; then
    echo "✅ 데이터베이스 삽입 완료"
else
    echo "❌ 데이터베이스 삽입 실패"
    exit 1
fi

echo "🎉 모든 더미 데이터 생성 및 삽입 완료!"
echo "📁 생성된 파일: dummy_data.json"
echo "📊 데이터베이스에 삽입된 데이터:"
echo "   - 사용자 프로필"
echo "   - 모구 게시물"
echo "   - 사용자 상호작용"
echo "   - 평가 데이터"
