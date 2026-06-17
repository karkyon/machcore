import {
  Injectable, CanActivate, ExecutionContext, ForbiddenException,
} from '@nestjs/common';

/**
 * ProgramSessionGuard
 * ====================
 * Work Session の JWT が発行された対象 mc_program_id / nc_program_id と、
 * 実際にリクエストされた URL パラメータ (:mc_id または :nc_id) が
 * 一致するかどうかを検証する。
 *
 * 背景:
 *   段取シートバック承認フロー等で発行された編集セッション(JWT)が、
 *   ブラウザの localStorage に残ったまま別のマシニング/NC情報画面へ
 *   遷移した場合、従来は再認証なしでその画面の編集・段取シート発行が
 *   できてしまっていた。これは JWT がどの mc_id/nc_id 用に発行された
 *   トークンかを一切検証していなかったことが原因。
 *
 * このガードは @UseGuards(AuthGuard('jwt'), ProgramSessionGuard) として
 * AuthGuard('jwt') の後に使用することを前提とする (req.user が必要)。
 *
 * 判定ルール:
 *   - req.user.mc_program_id が設定されている場合、URLの :mc_id と一致しなければ拒否
 *   - req.user.nc_program_id が設定されている場合、URLの :nc_id と一致しなければ拒否
 *   - どちらも未設定 (旧トークン/管理者ログイン等) の場合は許可する
 *     (後方互換性のため。管理者ログイントークンには program_id が無い)
 */
@Injectable()
export class ProgramSessionGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const req = context.switchToHttp().getRequest();
    const user = req.user;
    if (!user) return true; // AuthGuard が先に弾くはずだが念のため

    const params = req.params || {};

    if (user.mc_program_id != null) {
      const urlMcId = params.mc_id != null ? parseInt(params.mc_id, 10) : null;
      if (urlMcId == null || urlMcId !== Number(user.mc_program_id)) {
        throw new ForbiddenException(
          'このセッションは別のマシニング情報用に発行されています。再認証してください。',
        );
      }
    }

    if (user.nc_program_id != null) {
      const urlNcId = params.nc_id != null ? parseInt(params.nc_id, 10) : null;
      if (urlNcId == null || urlNcId !== Number(user.nc_program_id)) {
        throw new ForbiddenException(
          'このセッションは別のNC情報用に発行されています。再認証してください。',
        );
      }
    }

    return true;
  }
}
