from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.exceptions import NotFound


class CustomPropertyPagination(PageNumberPagination):
    page_size = 2
    page_size_query_param = 'page_size'
    max_page_size = 10000
    page_query_param = 'page'

    def paginate_list(self, data, page_number, page_size):
        total_count = len(data)
        start_index = (page_number - 1) * page_size
        end_index = start_index + page_size
        paginated_data = data[start_index:end_index]
        total_page_number = (total_count + page_size - 1) // page_size
        return paginated_data, total_page_number

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request

        # Set page_size from query parameter if provided
        self.page_size = self.get_page_size(request)

        # Extract page number from query parameters and ensure it's an integer
        try:
            self.page_number = int(request.query_params.get(self.page_query_param, 1))
        except ValueError:
            raise NotFound(detail="Invalid page number format.")

        total_count = len(queryset)
        print(queryset)
        start_index = (self.page_number - 1) * self.page_size
        end_index = start_index + self.page_size

        if start_index >= total_count or start_index < 0:
            raise NotFound(detail="Invalid page.")

        paginated_data = queryset[start_index:end_index]
        self.total_page_number = (total_count + self.page_size - 1) // self.page_size

        return list(paginated_data)

    def get_paginated_response(self, data):
        request = self.request

        # Set page_size from query parameter if provided
        page_size = self.page_size
        if request.query_params.get(self.page_size_query_param):
            page_size = int(request.query_params.get(self.page_size_query_param, page_size))

        # Extract page number from query parameters and ensure it's an integer
        try:
            page_number = int(request.query_params.get(self.page_query_param, 1))
        except ValueError:
            raise NotFound(detail="Invalid page number format.")

        resource_type = "Bundle"
        resource_url = request.build_absolute_uri().split('?')[0]
        resource_type_group = "Group"

        identifiers = []
        quantity = 0
        name = ""
        type_value = ""
        actual = ""
        members = []

        if isinstance(data, list):
            for item in data:
                quantity = item.get("quantity", quantity)
                name = item.get("name", name)
                type_value = item.get("type", type_value)
                actual = item.get("actual", actual)
                members.extend(item.get("member", []))
                identifiers.extend(item.get("identifier", []))

        paginated_data, total_page_number = self.paginate_list(members, page_number, page_size)

        # Raise error if page number is out of range
        if page_number > total_page_number or page_number < 1:
            raise NotFound(detail="Invalid page.")

        member_url = f"{resource_url}?{self.page_query_param}="

        links = [
            {"relation": "self", "url": f"{member_url}{page_number}"},
            {"relation": "first", "url": f"{member_url}1"},
            {"relation": "last", "url": f"{member_url}{total_page_number}"},
        ]
        if page_number < total_page_number:
            links.append({"relation": "next", "url": f"{member_url}{page_number + 1}"})
        if page_number > 1:
            links.append({"relation": "previous", "url": f"{member_url}{page_number - 1}"})

        return Response({
            "resourceType": resource_type,
            "type": "searchset",
            "total": len(members),
            "links": links,
            "entry": {
                "resourceType": resource_type_group,
                "identifier": identifiers,
                "name": name,
                "quantity": quantity,
                "type": type_value,
                "actual": actual,
                "member": paginated_data
            }
        })
