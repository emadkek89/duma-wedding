# 듬아의 웨딩사전

DumA WEDDING DICTIONARY는 듬아의 웨딩툰과 유튜브 콘텐츠를 주제별로 찾는 정적 사이트입니다. 방문자는 가입 없이 검색하고 인스타그램과 유튜브에서 원본을 볼 수 있습니다. 사이트에는 분석에 사용한 본문, 자막, 전체 이미지가 포함되지 않습니다.

## 처음 공개하기

1. GitHub에서 변경 사항이 담긴 PR을 열고 내용을 확인한 뒤 **Merge pull request**를 누릅니다.
2. 저장소 **Settings → Pages**에서 **Build and deployment → Source**를 **GitHub Actions**로 선택합니다.
3. **Settings → Actions → General → Workflow permissions**에서 자동 수집 결과를 저장할 수 있도록 **Read and write permissions**를 허용합니다. 조직 정책이 이 선택을 막거나 `main` 브랜치가 자동 커밋을 막으면 관리자에게 설정을 확인해 달라고 요청하세요. 이 권한은 수집 데이터를 저장하는 작업에 쓰입니다.
4. **Actions → 웨딩사전 업데이트 → Run workflow**에서 `main`을 선택해 실행합니다. 채널을 아직 연결하지 않았어도 초기 5개로 배포할 수 있습니다. 완료 뒤 **Settings → Pages** 또는 해당 실행의 **GitHub Pages 배포** 단계에서 실제 주소를 확인하세요.

공개 저장소의 GitHub Pages와 표준 GitHub Actions 러너를 사용합니다. 별도 서버, 데이터베이스, 유료 AI API는 필요 없습니다. 비공개 저장소에서 Pages를 공개할 수 있는지와 Actions 사용량 정책은 계정 플랜에 따라 달라집니다.

## 유튜브 연결

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트를 만들거나 선택합니다.
2. **API 및 서비스 → 라이브러리**에서 **YouTube Data API v3**를 찾아 사용 설정합니다. **사용자 인증 정보 → 사용자 인증 정보 만들기 → API 키**에서 키를 만들고 API 제한은 **YouTube Data API v3**로 설정합니다. 기본 무료 할당량으로 시작하고 할당량 증설은 따로 신청하지 않아도 됩니다.
3. GitHub 저장소 **Settings → Secrets and variables → Actions → Secrets → New repository secret**에서 이름을 `YOUTUBE_API_KEY`로 설정하고 방금 만든 키를 입력합니다. 이 키는 공식 API에서 `@듬아` 채널과 업로드 목록을 조회하는 데 사용됩니다.
4. 채널을 찾지 못하면 해당 YouTube 계정에서 **설정 → 고급 설정**의 `UC`로 시작하는 채널 ID를 확인합니다. GitHub **Settings → Secrets and variables → Actions → Variables**에 `YOUTUBE_CHANNEL_ID`로 등록합니다. 키 없이 이 변수만 등록하면 공개 RSS에서 최근 게시물만 수집합니다.
5. **Actions → 웨딩사전 업데이트 → Run workflow**에서 **과거 게시물 전체 수집**을 체크해 최초 수집을 실행합니다. Data API는 업로드 목록을 페이지 끝까지 읽습니다. RSS는 피드에서 제공하는 최근 게시물만 읽습니다.

YouTube Data API는 쇼츠 여부를 전용 필드로 제공하지 않습니다. 명시적인 쇼츠 링크·태그·해시태그가 있는 게시물은 쇼츠로 분류합니다. 표시가 없는 영상은 **유튜브 보기**로 표시되며 검토 후 `platform`을 `shorts`로 수정할 수 있습니다. 사이트에서 영상 길이만으로 쇼츠 여부를 추측하지 않습니다.

## 인스타그램 연결과 갱신

1. `duma.toon`을 비즈니스 또는 크리에이터 계정으로 설정합니다. [Meta for Developers](https://developers.facebook.com/)에서 앱을 만들고 **Instagram API with Instagram Login**을 추가합니다.
2. 앱 대시보드의 Instagram API 설정에서 `duma.toon`을 연결합니다. 개발 모드에서 테스터 초대가 필요하면 해당 계정으로 수락한 뒤 다시 연결하세요. 계정과 미디어 읽기에는 `instagram_business_basic` 권한을 사용합니다. 앱 역할 밖의 계정은 Meta의 앱 검수 또는 추가 승인이 필요할 수 있습니다.
3. Meta에서 제공하는 연결 화면으로 해당 계정의 토큰을 발급합니다. 단기 토큰을 받았다면 [Meta 공식 토큰 문서](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login/)의 장기 토큰 교환 절차를 따릅니다. 앱 화면이 별도 Graph API 버전을 지정하면 GitHub **Actions → Variables**에 `META_GRAPH_VERSION`으로 입력합니다.
4. GitHub 저장소 **Settings → Secrets and variables → Actions → Secrets → New repository secret**에서 `INSTAGRAM_ACCESS_TOKEN`을 만들고 토큰을 넣습니다. 토큰을 파일, 이슈, 채팅에 붙여넣지 마세요.
5. **Actions → 웨딩사전 업데이트 → Run workflow**에서 **과거 게시물 전체 수집**을 체크해 실행합니다. 실행 요약에서 인스타그램이 정상인지 확인합니다.
6. 만료 전에 Meta 공식 갱신 절차로 유효한 장기 토큰을 갱신하거나, 만료되었다면 계정을 다시 인증해 토큰을 발급합니다. GitHub의 같은 Secrets 화면에서 기존 `INSTAGRAM_ACCESS_TOKEN` 값을 교체하고 **Run workflow**로 확인합니다. Meta 장기 토큰은 일반적으로 약 60일간 유효하며 자동 갱신은 설정되어 있지 않습니다.

인스타그램의 미디어 URL에는 만료되는 주소가 있을 수 있습니다. 이미지 로딩에 실패하면 카드가 텍스트로 표시됩니다. 과거 게시물의 주소를 다시 조회하려면 전체 수집을 실행하세요.

## 자동 업데이트와 분석 범위

- 매일 한국시간 오전 9시 예약 실행입니다. GitHub Actions 부하에 따라 시작이 지연될 수 있습니다. 수동 실행은 같은 화면의 **Run workflow** 메뉴를 사용합니다. 일상 실행은 각 채널의 최신 페이지를 조회하며, 오래된 항목은 전체 수집으로 보완할 수 있습니다.
- 제목, 설명, 해시태그와 선택적으로 읽을 수 있는 자막·이미지 문자를 규칙으로 분석합니다. 유튜브의 웨딩 관련성이 불명확하거나 인스타그램 글에서 주제 단서를 확보하지 못하면 검토 대기로 둡니다. 미확인 콘텐츠의 제목이나 썸네일을 만들어 넣지 않습니다.
- 이미지 OCR은 GitHub **Actions → Variables**에서 `ENABLE_OCR`을 `1`로 설정하면 무료 Tesseract 한글·영문 인식기를 사용합니다. 인스타툰 표지와 API가 반환한 캐러셀 이미지, 유튜브 썸네일을 처리합니다. 전체 수집의 실행 시간이 늘어날 수 있습니다.
- 자막은 계정에 편집 권한이 있고 공식 API가 자막을 제공하는 경우에만 읽습니다. 필요할 때 YouTube 소유자 OAuth 액세스 토큰을 `YOUTUBE_CAPTIONS_ACCESS_TOKEN` Secret으로 입력할 수 있습니다. 단기 토큰의 자동 갱신은 설정되어 있지 않습니다. 일반 공개 영상의 자막을 우회 수집하지 않습니다.
- 동일한 게시물 ID는 한 번만 등록됩니다. 원제목 또는 인스타그램 본문의 짧은 첫 줄이 일치하고 구체적인 카테고리가 겹치는 서로 다른 플랫폼 자료를 자동 병합합니다. 첫 줄은 내용 대신 비교용 해시만 저장합니다. 제목 정리 후 동일하게 보이는 다른 결과는 실행 요약에 병합 후보로 표시합니다.
- 채널 조회 중 오류가 발생하면 그 채널의 기존 데이터가 유지됩니다. 다른 채널이 성공하면 그 결과는 저장·배포되고 실행은 실패로 표시됩니다. 마지막 정상 업데이트는 연결된 채널 중 하나 이상을 조회했고 모두 성공한 날짜입니다.
- 공개 Pages 아티팩트에는 HTML, CSS, JavaScript, 검색용 JSON만 포함합니다. 검색을 위해 제목·카테고리·키워드와 정렬용 날짜는 브라우저로 전달합니다. 전체 본문, 원본 제목 기록, 운영 검토 정보, 자막은 배포하지 않습니다. GitHub가 공개 저장소라면 저장소의 파생 검토 기록과 Actions 요약은 GitHub에서 읽을 수 있으므로 민감한 정보를 기록하지 마세요.

## 분류 수정과 검토

**Actions → 웨딩사전 업데이트 → 최근 실행 → Summary**에서 채널 상태, 최근 게시물, 검토 대기, 병합 후보를 확인할 수 있습니다. GitHub에서 파일을 직접 편집하거나 Codex에 콘텐츠 ID와 원하는 수정을 알려주세요. 쓰기 권한이 있는 운영자만 수정할 수 있습니다.

`catalog/overrides.json`은 자동 수집에서 변경하지 않습니다. 아래 예처럼 `items` 안에 등록 ID를 넣어 제목, 카테고리, 키워드를 바꿀 수 있습니다. 자동 수집 데이터의 ID는 유튜브 `yt:영상ID`, 인스타그램 `ig:게시물코드`이며, 날짜와 원제목은 `catalog/state.json`에서 확인할 수 있습니다.

```json
{
  "items": {
    "yt:yhgTtVzNlPs": {
      "title": "웨딩촬영 헤어변형 꼭 해야 할까?",
      "categories": ["헤어·메이크업", "스튜디오"],
      "keywords": ["헤어변형", "웨딩촬영 헤어"],
      "topic": "촬영-헤어변형",
      "status": "published"
    }
  },
  "topics": {}
}
```

- **병합**하려면 각 원본 항목에 같은 `topic` 값을 입력합니다. **분리**하려면 서로 다른 값을 넣습니다.
- **숨김**은 항목의 `status`를 `hidden`으로, **검토 후 공개**는 `published`로 설정합니다. 제목이 비어 있는 항목을 공개할 때는 확인한 제목을 함께 입력하세요.
- 묶은 주제 전체의 제목이나 키워드를 수정하려면 `topics` 아래에 해당 `topic` 값을 키로 사용하고 `title`, `categories`, `keywords`를 입력합니다. `hidden: true`로 주제 전체를 숨길 수 있습니다.
- 새로운 카테고리는 `catalog/rules.json`의 기존 목록과 비교해 중복이 없는 경우 추가하세요. 기존 항목에 새 규칙을 적용하려면 전체 수집을 다시 실행합니다.

## 로컬 개발

Python 3.12에서 다음 명령으로 빌드하고 결과를 열 수 있습니다. 패키지 설치나 API 인증은 기본 사이트 빌드에 필요하지 않습니다.

```sh
python3 scripts/catalog.py build
python3 -m http.server 8000 --directory dist
```

브라우저에서 `http://localhost:8000`을 엽니다. 사이트 디자인과 동작은 `site/`, 초기 등록 및 관리 데이터는 `catalog/`, 수집·빌드는 `scripts/catalog.py`에 있습니다.
