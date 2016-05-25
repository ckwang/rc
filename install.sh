#!/bin/zsh
# This script installs the necessary vim plugins and create symlinks to any desired dotfiles

## Variables
HOMEDIR=${ZDOTDIR:-$HOME}
SOURCEDIR=$(dirname $0)
VIMDIR=$SOURCEDIR/vim
PREZTODIR=$SOURCEDIR/zprezto

# run necessary submodules
cd $SOURCEDIR
git submodule update --init --recursive
cd -

### SETUP Prezto
ln -s $PREZTODIR $HOMEDIR/.zprezto
setopt EXTENDED_GLOB
for rcfile in "${HOMEDIR}"/.zprezto/runcoms/^README.md(.N); do
  ln -s "$rcfile" "${HOMEDIR}/.${rcfile:t}"
done

### SETUP VIM
# create symlinks
ln -s $VIMDIR $HOMEDIR/.vim
ln -s $VIMDIR/vimrc $HOMEDIR/.vimrc
ln -s $VIMDIR/gvimrc $HOMEDIR/.gvimrc

# install vim plugins through Vundle
vim +PlugInstall +qall

### SETUP gitconfig
ln -s gitconfig $HOMEDIR/.gitconfig
