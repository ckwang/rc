#!/bin/zsh
# This script installs the necessary vim plugins and create symlinks to any desired dotfiles

## Variables
SOURCEDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VIMDIR=$SOURCEDIR/vim
PREZTODIR=$SOURCEDIR/zprezto

# run necessary submodules
(cd $SOURCEDIR ; git submodule update --init --recursive)

### SETUP Prezto
ln -ihFs $PREZTODIR $HOME/.zprezto
setopt EXTENDED_GLOB
for rcfile in "${HOME}"/.zprezto/runcoms/^README.md(.N); do
  ln -is "$rcfile" "${HOME}/.${rcfile:t}"
done

### SETUP VIM
# create symlinks
mkdir -p ${XDG_CONFIG_HOME:=$HOME/.config}
ln -ihFs $VIMDIR $XDG_CONFIG_HOME/nvim
ln -ihFs $VIMDIR $HOME/.vim
ln -is $VIMDIR/vimrc $HOME/.vimrc
ln -is $VIMDIR/gvimrc $HOME/.gvimrc

# install vim plugins through Vundle
nvim +PlugUpdate +qall

### SETUP gitconfig
ln -is $SOURCEDIR/gitconfig $HOME/.gitconfig
