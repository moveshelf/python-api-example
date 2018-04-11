import argparse
import logging

from api import MoveshelfApi, Metadata

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    api = MoveshelfApi()

    def getUserProjects(args):
        for p in api.getUserProjects():
            print(p)

    def uploadFile(args):
        clip_id = api.uploadFile(args.filePath, args.project, Metadata(**vars(args)))
        print("Created new clip with ID: {}".format(clip_id))

    parser = argparse.ArgumentParser()
    sub_parsers = parser.add_subparsers()

    list_parser = sub_parsers.add_parser('list', help="List user projects")
    list_parser.set_defaults(func=getUserProjects)

    upload_parser = sub_parsers.add_parser('up', help="Upload file")
    upload_parser.add_argument('filePath', help="Path of file to upload")
    upload_parser.add_argument('project', help='Project to add file to. See "list"')
    upload_parser.add_argument('--title', help="Title of clip")
    upload_parser.add_argument('--description', help="Description of clip")
    upload_parser.add_argument('--allowDownload', help="Allow download of original data", action="store_true")
    upload_parser.add_argument('--allowUnlistedAccess', help="Allow access to preview to anyone in possesion of URL", action="store_true")
    upload_parser.set_defaults(func=uploadFile)

    args = parser.parse_args()
    args.func(args)
