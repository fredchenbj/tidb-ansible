#!/bin/bash

#######################################################################
# @file: code-commit.sh
# @author: duyuqi(duyuqi@yidian-inc.com)
# @date: 2018-07-30
# @brief:
#######################################################################


APP_DIR=$(dirname $0)
MOD_DIR=$(cd $APP_DIR/..; pwd)
root=$(dirname $0)
root=$(cd $root; pwd)

set -e

msg="$1"
branch=$(git branch | awk '{if($1=="*")print $2}')
if [ x"$msg" != x"" ]; then
	git commit -am "$msg"
	git fetch
	git rebase origin/$branch
fi
git push origin $branch

# vim: set expandtab ts=4 sw=4 sts=4 tw=100: #
