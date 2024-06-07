import json
import os
from typing import List
from pikpak import PikPak, crete_invite
from captcha.chmod import open_url2token
import config.config as config
import asyncio
import alist.alist as alist
from mail.mail import get_new_mail_code
import time
import logging
from rclone import conifg_2_pikpak_rclone, get_save_json_config, save_config, PikPakJsonData

# logger = logging.getLogger(os.path.splitext(os.path.split(__file__)[1])[0])
logger = logging.getLogger("main")


def get_start_share_id(pikpak: PikPak = None):
    try:
        pikpak_api = pikpak.pikpakapi
        # 创建一个事件循环thread_loop
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        main_loop = asyncio.get_event_loop()
        get_future = asyncio.ensure_future(pikpak_api.login())
        main_loop.run_until_complete(get_future)
        # 获取Pack From Shared的id
        get_future = asyncio.ensure_future(
            pikpak_api.path_to_id("Pack From Shared"))
        main_loop.run_until_complete(get_future)
        result = get_future.result()
        if len(result) == 1:
            id_Pack_From_Shared = result[-1].get("id")
            # 获取Pack From Shared文件夹下的所有文件夹
            get_future = asyncio.ensure_future(
                pikpak_api.file_list(parent_id=id_Pack_From_Shared))
            main_loop.run_until_complete(get_future)
            result = get_future.result()
            if len(result.get("files")) <= 0:
                id_Pack_From_Shared = None
        else:
            id_Pack_From_Shared = None

        # 获取Pack From Shared文件夹下的所有文件夹
        get_future = asyncio.ensure_future(
            pikpak_api.file_list(parent_id=id_Pack_From_Shared))
        main_loop.run_until_complete(get_future)
        result = get_future.result()

        # 需要分享的文件夹id
        fils_id = []
        for file in result.get("files"):
            if file.get("name") == 'My Pack' or file.get("name") == 'Pack From Shared':
                pass
            else:
                fils_id.append(file.get("id"))
        # for file in invite.get("share", []):
        #     get_future = asyncio.ensure_future(pikpak_api.path_to_id(file))
        #     main_loop.run_until_complete(get_future)
        #     result = get_future.result()
        #     fils_id.append(result[-1].get("id"))
        get_future = asyncio.ensure_future(
            pikpak_api.file_batch_share(fils_id, expiration_days=7)
        )
        main_loop.run_until_complete(get_future)
        result = get_future.result()
        logger.debug(result)
        return result.get("share_id", None)
    except:
        logger.error("分享失败 重新分享")
        time.sleep(30)
        return get_start_share_id(pikpak)


class BasePikpak:
    opation_pikpak_go: PikPak = None

    def pop_not_vip_pikpak(self):
        pass

    def save_pikpak_2(self, pikpak_go: PikPak):
        pass


class AlistPikpak(BasePikpak):
    pikpak_user_list: List[dict] = None
    alist_go: alist.Alist = None

    def __init__(self):
        self.alist_go = alist.Alist()
        self.alist_go.saveToNowConif()
        self.pikpak_user_list = self.alist_go.get_all_pikpak_storage()

    # 直接pop一个Alsit中的一个Vip的剩余天数小于0的pikpak登陆
    def pop_not_vip_pikpak(self) -> PikPak:
        if len(self.pikpak_user_list) <= 0:
            return None
        if self.pop_pikpak().get_vip_day_time_left() <= 0:
            return self.opation_pikpak_go
        else:
            return self.pop_not_vip_pikpak()

    # 直接pop一个Alsit中的一个pikpak登陆
    def pop_pikpak(self) -> PikPak:
        pikpak_data = self.pikpak_user_list.pop(0)
        self.opation_pikpak_go = PikPak(
            mail=pikpak_data.get("username"),
            pd=pikpak_data.get("password"),
        )
        return self.opation_pikpak_go

    def save_pikpak_2(self, pikpak_go: PikPak):
        storage_list = self.alist_go.get_storage_list()
        for data in storage_list.get("content"):
            addition = json.loads(data.get("addition"))
            if addition.get("username") == self.opation_pikpak_go.mail:
                addition["username"] = pikpak_go.mail
                addition["password"] = pikpak_go.pd
                data["addition"] = json.dumps(addition)
                logger.debug(data)
                self.alist_go.update_storage(data)
            logger.debug(addition)


class RclonePikpak(BasePikpak):
    rclone_conifgs: List[dict] = []
    rclone = None
    config_index = -1

    def __init__(self) -> None:
        self.rclone_conifgs = get_save_json_config()

    def pop_not_vip_pikpak(self) -> PikPak:
        try:
            self.config_index += 1
            self.rclone = conifg_2_pikpak_rclone(
                self.rclone_conifgs[self.config_index])
        except:
            self.rclone = None
            return None
        rclone_info = self.rclone.get_info()
        if rclone_info:
            if rclone_info.get("VIPType") == "novip":
                self.opation_pikpak_go = PikPak(
                    self.rclone.user, self.rclone.password)
                return self.opation_pikpak_go
            else:
                return self.pop_not_vip_pikpak()
        else:
            self.opation_pikpak_go = PikPak(
                mail=self.rclone.user, pd=self.rclone.password)
            if self.opation_pikpak_go.get_vip_day_time_left() <= 0:
                return self.opation_pikpak_go
            else:
                return self.pop_not_vip_pikpak()

    def save_pikpak_2(self, pikpak_go: PikPak):
        if self.rclone.user == pikpak_go.mail:
            logger.info(f"保存pikpak rclone中的账号和现在的账号时同一个这里不做修改")
            return

        self.rclone.user = pikpak_go.mail
        self.rclone.password = pikpak_go.pd
        self.rclone.save_self_2_config()
        data = self.rclone_conifgs[self.config_index]
        data["pikpak_user"] = pikpak_go.mail
        data["pikpak_password"] = pikpak_go.pd
        logger.debug(self.rclone_conifgs)
        save_config(self.rclone_conifgs)


def main():
    logger.info("开始执行Alist中的存储检测")
    alistPikpak: BasePikpak = config.alist_enable and AlistPikpak() or RclonePikpak()
    pikpak_go = alistPikpak.pop_not_vip_pikpak()
    while pikpak_go:
        invite_code = pikpak_go.get_self_invite_code()
        logger.info(f"注册新号填写邀请到:\n{pikpak_go.mail}\n邀请码:\n{invite_code}")
        pikpak_go_new = crete_invite(invite_code)
        if not pikpak_go_new:
            logger.debug("新建的号有误")
            logger.info(f"注册新号失败。。。。。。。。")
            break
        if pikpak_go.get_vip_day_time_left() > 0:
            logger.info(f"账号{pikpak_go.mail}现在已经是会员了")
            pikpak_go = alistPikpak.pop_not_vip_pikpak()
        if not pikpak_go:
            break
        if pikpak_go_new.get_vip_day_time_left() <= 0:
            continue
        logger.info(
            f"把账号:{pikpak_go.mail},中的所有数据分享到新的账号:{pikpak_go_new.mail} 上")
        share_id = get_start_share_id(pikpak_go)
        pikpak_go_new.set_proxy(None)
        pikpak_go_new.save_share(share_id)
        alistPikpak.save_pikpak_2(pikpak_go_new)
        # 新的获取新没有vip的pikpak
        pikpak_go = alistPikpak.pop_not_vip_pikpak()
    logger.info("Over")


def copye_list_2_rclone_config():
    """复制alist的配置到rclone的配置json配置中
    """
    alist_server = alist.Alist()
    # alist_server.saveToNowConif()
    rclone_configs: List[PikPakJsonData] = []
    for _alist in alist_server.get_storage_list()["content"]:
        if _alist.get("driver") == "PikPak":
            alist_mount_path = _alist.get("mount_path")[1:]
            addition = json.loads(_alist.get("addition"))
            rclone_json_data = PikPakJsonData({
                "remote": "pikpak_" + alist_mount_path,
                "pikpak_user": addition.get("username"),
                "pikpak_password": addition.get("password"),
                "mout_path": os.path.join(config.rclone_mount, alist_mount_path)
            })
            rclone_configs.append(rclone_json_data)
    logger.debug(rclone_configs)
    save_config(rclone_configs)


if __name__ == "__main__":
    config.set_captcha_callback(open_url2token)
    config.set_email_verification_code_callback(get_new_mail_code)
    main()
    # alistPikpak = AlistPikpak()
    # pikpak_go = alistPikpak.pop_not_vip_pikpak()
    # invite_code = pikpak_go.get_self_invite_code()
    # pikpak_go_new = crete_invite(invite_code)
    # get_start_share_id("mwrtye3718@tenvil.com","098poi")
    # https://mypikpak.com/s/VNzDxRlK3CYk0Z6HfkzTEw1uo1
    # pikpak = crete_invite(78269860)
    # logger.debug(pikpak)

    # rclone_conifgs = get_save_json_config()
    # print(rclone_conifgs)
    # index = 1
    # rclone = rclone_conifgs[index]
    # data = rclone_conifgs[index]
    # data["pikpak_user"] = data["pikpak_user"]+"0909090"
    # # rclone.update(data)
    # print(rclone_conifgs)
    copye_list_2_rclone_config()
