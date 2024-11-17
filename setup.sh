#!/bin/bash

DEFAULT_LCG_RELEASE="105c"
ANALYSIS_BASE_VERSION="24.2.39"

get_script_dir() {
    local SOURCE="${BASH_SOURCE[0]}"
    while [ -h "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
        local DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
        SOURCE="$(readlink "$SOURCE")"
        [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE" # if $SOURCE was a relative symlink, resolve it relative to the path where the symlink file was located
    done
    DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
    echo "$DIR"
}

find_lcg_versions() {
    local LCG_VERSION=$1

    # Get the machine architecture
    local ARCH=$(uname -m)

    # Convert architecture to match LCG subdirectory format
    case "$ARCH" in
        x86_64)
            ARCH="x86_64"
            ;;
        aarch64)
            ARCH="aarch64"
            ;;
        *)
            echo "Unsupported architecture: $ARCH"
            return 1
            ;;
    esac

    # Get the Linux distribution
    local DISTRO=""
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        # Extract the leading number from VERSION_ID
        local VERSION_MAJOR=${VERSION_ID%%.*}
        case "$ID" in
            centos)
                DISTRO="centos${VERSION_MAJOR}"
                ;;
            rhel|el|elma|almalinux)
                DISTRO="el${VERSION_MAJOR}"
                ;;
            *)
                echo "Unsupported Linux distribution: $ID" >&2
                return 1
                ;;
        esac
    else
        echo "Cannot determine Linux distribution." >&2
        return 1
    fi

    # Directory where LCG releases are stored
    local LCG_DIR="/cvmfs/sft.cern.ch/lcg/views/$LCG_VERSION"

    # Check if the directory exists
    if [ ! -d "$LCG_DIR" ]; then
        echo "LCG version $LCG_VERSION does not exist." >&2
        return 1
    fi

    # List and filter appropriate subdirectories
    local VALID_VERSIONS=$(ls -d "$LCG_DIR"/* | xargs -n 1 basename | grep -E "^$ARCH-$DISTRO-gcc[0-9]+-(opt|dbg)$")

    # If no valid versions are found, exit
    if [ -z "$VALID_VERSIONS" ]; then
        echo "No compatible versions found for architecture $ARCH and distribution $DISTRO." >&2
        return 1
    fi

    # Sort by GCC version (descending), then by type (opt first)
    local SORTED_VERSIONS=$(echo "$VALID_VERSIONS" | sort -t- -k3,3r -k4,4r -k4,4 -s)

    # Return the sorted versions
    echo "$SORTED_VERSIONS"
}


remove_duplicate_paths() {
    local path_value="$1"
    
    # Convert the input path string into an array using ':' as the delimiter
    IFS=':' read -r -a path_array <<< "$path_value"

    # Initialize an empty array for storing unique paths
    unique_paths=()

    for path in "${path_array[@]}"; do
        # Check if the path is already in unique_paths
        if [[ ! " ${unique_paths[*]} " == *" $path "* ]]; then
            unique_paths+=("$path")
        fi
    done

    # Join the array back into a single string and output the cleaned path
    echo "$(IFS=:; echo "${unique_paths[*]}")"
}

if [ "$#" -ge 1 ];
then
    LCG_RELEASE=LCG_$1
else
    LCG_RELEASE=LCG_$DEFAULT_LCG_RELEASE
fi

export DIR=$(get_script_dir)

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source ${ATLAS_LOCAL_ROOT_BASE}/user/atlasLocalSetup.sh

LCG_VERSION=$(find_lcg_versions "$LCG_RELEASE" | head -n 1)

if [ -z "$LCG_VERSION" ]; then
    echo "Failed to find suitable version for the LCG release: $LCG_RELEASE" >&2
    return 1
fi

lsetup "views $LCG_RELEASE $LCG_VERSION"
#asetup ${ANALYSIS_BASE_VERSION},AthAnalysis

lsetup emi
lsetup panda
lsetup rucio
lsetup PyAMI

export DERIVATIONTOOL_DIR=${DIR}
export PATH=${DIR}/bin:${PATH}
export PYTHONPATH=${DIR}:${PYTHONPATH}

export PATH=$(remove_duplicate_paths "$PATH")
export PYTHONPATH=$(remove_duplicate_paths "$PYTHONPATH")
