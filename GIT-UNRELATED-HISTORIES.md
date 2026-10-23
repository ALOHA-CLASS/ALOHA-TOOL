# Git pull: unrelated histories 해결 방법

## 발생한 오류

```powershell
git pull --tags main main
```

```text
fatal: refusing to merge unrelated histories
```

## 원인

로컬 저장소와 원격 저장소가 서로 독립적으로 초기화되어 공통 조상 커밋이 없었습니다.
얕은 복제(shallow clone) 문제는 아니었습니다.

- 로컬 `main`: `f0e8de8` (`INIT`)
- 원격 추적 브랜치 `main/main`: `79e4663` (`Initial commit`)
- 원격 저장소: `https://github.com/ALOHA-CLASS/ALOHA-TOOL.git`

이 저장소에서는 원격 이름과 브랜치 이름이 모두 `main`입니다.
따라서 `git pull --tags main main`의 첫 번째 `main`은 원격 이름,
두 번째 `main`은 원격 브랜치 이름입니다. `main/main`은 해당 원격 추적 브랜치입니다.

## 실제 해결 과정

작업 트리가 깨끗한지, 원격 주소가 올바른지, 두 커밋 사이에 공통 조상이 없는지 확인했습니다.
원격에는 루트 `README.md`만 있었으며 로컬 파일과의 충돌은 없었습니다.

### 1. 상태 및 이력 확인

```powershell
git status --short --branch
git remote -v
git branch -vv
git rev-parse --is-shallow-repository
git log --all --graph --oneline --decorate -18
git merge-base main main/main
```

`git merge-base`가 공통 조상을 출력하지 않고 종료 코드 1을 반환하는 것은
이 경우 공통 이력이 없다는 뜻입니다.

### 2. 최신 원격 이력과 태그 가져오기

```powershell
git fetch --tags main
```

### 3. 병합 전 로컬 이력 백업

```powershell
git branch backup/main-before-unrelated-histories-20261023 HEAD
```

이 백업 브랜치는 병합 전 로컬 커밋을 보존합니다. 미커밋 파일을 백업하는 기능은
아니므로 작업 트리에 변경사항이 있다면 먼저 별도로 보존해야 합니다.
같은 이름의 브랜치가 이미 있다면 덮어쓰지 말고 다른 이름을 사용합니다.

### 4. 두 이력을 명시적으로 병합

```powershell
git -c core.editor=true merge --no-edit --no-ff --allow-unrelated-histories main/main -m "Merge remote main history with local main" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

`--allow-unrelated-histories`는 공통 조상이 없는 두 이력의 병합을 허용합니다.
기존 로컬 커밋과 원격 커밋을 모두 유지하며 병합 커밋을 생성합니다.
이 옵션을 전역 설정으로 추가하지 않고 이번 병합에만 사용했습니다.

다른 상황에서 충돌이 발생하면 충돌 파일을 수정하고 해당 파일만 `git add`한 뒤
`git merge --continue`로 완료합니다. 완료 전 병합을 취소하려면
`git merge --abort`를 사용합니다. 명령이 실패한 경우 다음 단계로 진행하기 전에
오류와 `git status`를 확인합니다.

## 해결 결과

- 병합 커밋: `ba75feb`
- 기존 로컬 파일과 두 최초 커밋 모두 보존
- 원격의 루트 `README.md` 추가
- 병합 직후 상태: `main...main/main [ahead 2]` (뒤처진 커밋 없음)
- 원격 push는 실행하지 않음

## 검증 방법

```powershell
git status --short --branch
git log -3 --graph --oneline
git merge-base --is-ancestor main/main HEAD
git merge-base --is-ancestor backup/main-before-unrelated-histories-20261023 HEAD
git diff --exit-code backup/main-before-unrelated-histories-20261023 HEAD -- IMG VIDEO
git pull --tags main main
```

두 `--is-ancestor` 명령은 각각 종료 코드 0이면 원격 이력과 기존 로컬 이력이
현재 브랜치에 포함되었음을 뜻합니다. `git diff`가 출력 없이 종료 코드 0이면
기존 이미지 및 동영상 도구 파일에 변경이 없다는 뜻입니다.
원격에 추가 변경이 없다면 마지막 pull은 `Already up to date.`로 끝납니다.

이 문서는 병합 이후 생성했으므로 별도로 커밋하기 전까지는 미추적 파일로 표시됩니다.

## 이후 사용할 명령

다음 pull부터는 공통 이력이 생겼으므로 기존 명령을 그대로 사용합니다.

```powershell
git pull --tags main main
```

문서를 커밋하고 로컬 결과를 원격에 반영하려면 내용을 검토한 후 다음을 실행합니다.
아래 문서 커밋과 push는 이번 해결 과정에서 실행하지 않았습니다.

```powershell
git add GIT-UNRELATED-HISTORIES.md
git commit -m "docs: document unrelated histories merge recovery" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push main main
```

일반 push가 거절되면 원격의 새 변경사항을 먼저 확인하고 통합해야 합니다.
이 오류를 해결하기 위해 강제 push나 `git reset --hard`를 사용할 필요는 없습니다.
